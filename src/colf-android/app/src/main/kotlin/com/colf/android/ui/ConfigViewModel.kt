package com.colf.android.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.colf.android.data.AppSettings
import com.colf.android.data.SettingsRepository
import com.colf.android.network.HealthResult
import com.colf.android.network.IngestApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/** Esito mostrato dopo "Testa connessione". */
sealed class ConnectionTestState {
    data object Idle : ConnectionTestState()
    data object Testing : ConnectionTestState()
    data object Ok : ConnectionTestState()
    data object Unauthorized : ConnectionTestState()
    data object Unreachable : ConnectionTestState()
    data object InvalidUrl : ConnectionTestState()
}

class ConfigViewModel(application: Application) : AndroidViewModel(application) {

    private val settingsRepository = SettingsRepository(application)
    private val ingestApi = IngestApi()

    val settings: StateFlow<AppSettings> = settingsRepository.settingsFlow.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000),
        initialValue = AppSettings(),
    )

    private val _connectionTestState = MutableStateFlow<ConnectionTestState>(ConnectionTestState.Idle)
    val connectionTestState: StateFlow<ConnectionTestState> = _connectionTestState.asStateFlow()

    fun setBaseUrl(value: String) = viewModelScope.launch { settingsRepository.setBaseUrl(value) }
    fun setToken(value: String) = viewModelScope.launch { settingsRepository.setToken(value) }
    fun setForwardingEnabled(value: Boolean) = viewModelScope.launch { settingsRepository.setForwardingEnabled(value) }

    fun setBankPackagesText(rawText: String) {
        val packages = rawText.lines()
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .toSet()
        viewModelScope.launch { settingsRepository.setBankPackages(packages) }
    }

    /**
     * Prova `/ingest/health`, ritentando qualche volta se il server risulta
     * irraggiungibile: la VPN è always-on, ma può essere in fase di
     * ri-aggancio (cambio wifi/4G, uscita da doze).
     */
    fun testConnection() {
        viewModelScope.launch {
            _connectionTestState.value = ConnectionTestState.Testing
            val current = settings.value

            runHealthChecks(current)
        }
    }

    private suspend fun runHealthChecks(current: AppSettings) {
        val totalAttempts = HEALTH_BACKOFF_MILLIS.size + 1
        for (attempt in 0 until totalAttempts) {
            val state = when (ingestApi.health(current.baseUrl, current.token)) {
                is HealthResult.Ok -> ConnectionTestState.Ok
                is HealthResult.Unauthorized -> ConnectionTestState.Unauthorized
                is HealthResult.InvalidUrl -> ConnectionTestState.InvalidUrl
                is HealthResult.Unreachable, is HealthResult.Unexpected -> ConnectionTestState.Unreachable
            }

            // Solo "irraggiungibile" può essere transitorio: gli altri esiti
            // sono definitivi, inutile ritentare.
            val isLastAttempt = attempt == totalAttempts - 1
            if (state != ConnectionTestState.Unreachable || isLastAttempt) {
                _connectionTestState.value = state
                return
            }
            delay(HEALTH_BACKOFF_MILLIS[attempt])
        }
    }

    fun resetConnectionTestState() {
        _connectionTestState.value = ConnectionTestState.Idle
    }

    private companion object {
        /** Attese tra un tentativo e l'altro: 4 tentativi in ~7s totali. */
        val HEALTH_BACKOFF_MILLIS = listOf(1_000L, 2_000L, 4_000L)
    }
}
