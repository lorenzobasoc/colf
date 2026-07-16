package com.colf.android.work

import android.content.Context
import android.util.Log
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkerParameters
import com.colf.android.data.SettingsRepository
import com.colf.android.network.IngestApi
import com.colf.android.network.IngestResult
import com.colf.android.network.NotificationPayload
import com.colf.android.wireguard.WireGuardController
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.delay

/**
 * Invia una notifica bancaria al server di ingest CoLF. Gira come
 * CoroutineWorker (WorkManager) così il lavoro sopravvive alla chiusura
 * dell'app e viene ripreso quando torna la rete, anche se il processo è
 * stato ucciso nel frattempo.
 *
 * Due livelli di retry:
 * 1) dentro doWork(), 5 tentativi con backoff 2s/4s/8s/16s tra un tentativo e
 *    l'altro (nessuna attesa dopo l'ultimo, che delega subito a WorkManager)
 *    per dare tempo al tunnel WireGuard di risalire dopo il broadcast intent;
 * 2) se anche questi falliscono, Result.retry() delega a WorkManager, che
 *    ritenta più avanti (con vincolo NetworkType.CONNECTED, backoff esponenziale
 *    a partire da 30s) anche se nel frattempo l'app è stata chiusa o il device
 *    è stato riavviato.
 */
class NotificationForwardWorker @JvmOverloads constructor(
    appContext: Context,
    params: WorkerParameters,
    private val settingsRepository: SettingsRepository = SettingsRepository(appContext),
    private val ingestApi: IngestApi = IngestApi(),
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val packageName = inputData.getString(KEY_PACKAGE) ?: return Result.failure()
        val title = inputData.getString(KEY_TITLE).orEmpty()
        val text = inputData.getString(KEY_TEXT).orEmpty()
        val postedAt = inputData.getString(KEY_POSTED_AT) ?: return Result.failure()

        val settings = settingsRepository.snapshot()
        if (!settings.isReadyToForward) {
            Log.i(TAG, "Inoltro disabilitato o configurazione incompleta: scarto la notifica")
            return Result.success()
        }

        WireGuardController.bringTunnelUp(applicationContext, settings.tunnelName)

        val payload = NotificationPayload(
            packageName = packageName,
            title = title,
            text = text,
            postedAt = postedAt,
        )

        val totalAttempts = BACKOFF_SCHEDULE_MILLIS.size + 1
        for (attempt in 0 until totalAttempts) {
            val result = ingestApi.postNotification(settings.baseUrl, settings.token, payload)
            Log.d(TAG, "Tentativo ${attempt + 1}/$totalAttempts: $result")

            when (result) {
                is IngestResult.Ok -> return Result.success()
                is IngestResult.Disabled -> {
                    Log.i(TAG, "Feature disattivata lato bot: non ritento")
                    return Result.success()
                }
                is IngestResult.Busy -> {
                    Log.i(TAG, "Spesa già in sospeso sul bot: non ritento")
                    return Result.success()
                }
                is IngestResult.Unauthorized -> {
                    Log.e(TAG, "Token errato: non ritento")
                    return Result.failure()
                }
                is IngestResult.BadRequest -> {
                    Log.e(TAG, "Payload rifiutato dal server: non ritento")
                    return Result.failure()
                }
                is IngestResult.InvalidUrl -> {
                    // Base URL vuoto o malformato: errore di configurazione, non
                    // transitorio. Ritentare non serve a niente e sveglierebbe la
                    // VPN all'infinito: fallisco subito.
                    Log.e(TAG, "Base URL non valido (${result.cause.message}): non ritento", result.cause)
                    return Result.failure()
                }
                is IngestResult.Unexpected -> {
                    Log.e(TAG, "Risposta inattesa (${result.code}): non ritento")
                    return Result.failure()
                }
                is IngestResult.ServerError, is IngestResult.NetworkFailure -> {
                    // Probabile tunnel VPN ancora giù o errore transitorio del server: ritento.
                    val isLastAttempt = attempt == totalAttempts - 1
                    if (isLastAttempt) {
                        Log.w(TAG, "Tentativi esauriti in questo run: delego il retry a WorkManager")
                        return Result.retry()
                    }
                    delay(BACKOFF_SCHEDULE_MILLIS[attempt])
                }
            }
        }
        return Result.retry()
    }

    companion object {
        private const val TAG = "NotificationForwardWorker"

        const val KEY_PACKAGE = "package"
        const val KEY_TITLE = "title"
        const val KEY_TEXT = "text"
        const val KEY_POSTED_AT = "posted_at"

        /**
         * Attese tra un tentativo e l'altro: 4 attese (2s/4s/8s/16s) per 5
         * tentativi totali (BACKOFF_SCHEDULE_MILLIS.size + 1). Nessuna attesa
         * dopo l'ultimo tentativo: si delega subito a WorkManager, che ha il
         * proprio backoff esponenziale (a partire da 30s, vedi buildRequest()).
         */
        val BACKOFF_SCHEDULE_MILLIS = listOf(2_000L, 4_000L, 8_000L, 16_000L)

        fun buildRequest(packageName: String, title: String, text: String, postedAt: String) =
            OneTimeWorkRequestBuilder<NotificationForwardWorker>()
                .setInputData(
                    Data.Builder()
                        .putString(KEY_PACKAGE, packageName)
                        .putString(KEY_TITLE, title)
                        .putString(KEY_TEXT, text)
                        .putString(KEY_POSTED_AT, postedAt)
                        .build(),
                )
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build(),
                )
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()
    }
}
