package com.colf.android.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.colf.android.data.AppSettings
import com.colf.android.data.SettingsRepository
import com.colf.android.network.HealthResult
import com.colf.android.network.IngestApi
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
    data object OkButDisabled : ConnectionTestState()
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
    fun setTunnelName(value: String) = viewModelScope.launch { settingsRepository.setTunnelName(value) }
    fun setForwardingEnabled(value: Boolean) = viewModelScope.launch { settingsRepository.setForwardingEnabled(value) }

    fun setBankPackagesText(rawText: String) {
        val packages = rawText.lines()
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .toSet()
        viewModelScope.launch { settingsRepository.setBankPackages(packages) }
    }

    fun testConnection() {
        viewModelScope.launch {
            _connectionTestState.value = ConnectionTestState.Testing
            val current = settings.value
            _connectionTestState.value = when (val result = ingestApi.health(current.baseUrl, current.token)) {
                is HealthResult.Ok -> if (result.enabled) ConnectionTestState.Ok else ConnectionTestState.OkButDisabled
                is HealthResult.Unauthorized -> ConnectionTestState.Unauthorized
                is HealthResult.Unreachable -> ConnectionTestState.Unreachable
                is HealthResult.Unexpected -> ConnectionTestState.Unreachable
                is HealthResult.InvalidUrl -> ConnectionTestState.InvalidUrl
            }
        }
    }

    fun resetConnectionTestState() {
        _connectionTestState.value = ConnectionTestState.Idle
    }
}
