package com.colf.android.notification

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import androidx.work.WorkManager
import com.colf.android.data.SettingsRepository
import com.colf.android.work.NotificationForwardWorker
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.concurrent.ConcurrentHashMap
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * Ascolta tutte le notifiche di sistema e inoltra al bot CoLF solo quelle
 * delle app bancarie configurate che sembrano un pagamento
 * ([NotificationFilter.isExpenseNotification]).
 *
 * Nessuna logica di business qui dentro oltre all'estrazione/filtro: l'invio
 * vero e proprio (con retry, VPN, ecc.) è delegato a [NotificationForwardWorker].
 */
class ColfNotificationListenerService : NotificationListenerService() {

    private val serviceScope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private lateinit var settingsRepository: SettingsRepository

    /**
     * Ultimo invio per chiave di deduplica; solo in memoria, si azzera se il
     * service viene ricreato. `ConcurrentHashMap` perché onNotificationPosted
     * lancia una coroutine per notifica su `Dispatchers.Default` (pool
     * multi-thread): letture/scritture concorrenti su una mutableMapOf
     * semplice non sono sicure. Le entry più vecchie della finestra di dedup
     * vengono potate a ogni inserimento (vedi [pruneExpiredDedupEntries]) per
     * evitare una crescita illimitata: il service resta vivo quanto il
     * processo.
     */
    private val lastSentAtByKey = ConcurrentHashMap<String, Long>()

    override fun onCreate() {
        super.onCreate()
        settingsRepository = SettingsRepository(applicationContext)
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        super.onNotificationPosted(sbn)

        // Scarta notifiche di gruppo/summary: non hanno un testo di pagamento reale.
        if (sbn.notification.flags and Notification.FLAG_GROUP_SUMMARY != 0) return

        val packageName = sbn.packageName
        val extras = sbn.notification.extras
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString()
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString()
        val bigText = extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString()
        val effectiveText = if (bigText != null && bigText.length > (text?.length ?: 0)) bigText else text

        if (effectiveText.isNullOrBlank()) return

        val postTime = sbn.postTime

        serviceScope.launch {
            try {
                val settings = settingsRepository.snapshot()
                if (!settings.forwardingEnabled) return@launch
                if (packageName !in settings.bankPackages) return@launch
                if (!NotificationFilter.isExpenseNotification(title, effectiveText)) return@launch

                val key = NotificationDeduplicator.keyFor(packageName, title, effectiveText)
                if (NotificationDeduplicator.isDuplicate(key, postTime, lastSentAtByKey)) {
                    Log.d(TAG, "Notifica duplicata entro la finestra di dedup, la scarto: $key")
                    return@launch
                }
                lastSentAtByKey[key] = postTime
                pruneExpiredDedupEntries(lastSentAtByKey, now = postTime)

                val postedAtIso = Instant.ofEpochMilli(postTime)
                    .atZone(ZoneId.systemDefault())
                    .format(DateTimeFormatter.ISO_LOCAL_DATE_TIME)

                val request = NotificationForwardWorker.buildRequest(
                    packageName = packageName,
                    title = title.orEmpty(),
                    text = effectiveText,
                    postedAt = postedAtIso,
                )
                WorkManager.getInstance(applicationContext).enqueue(request)
                Log.i(TAG, "Notifica da $packageName accodata per l'inoltro")
            } catch (e: Exception) {
                Log.e(TAG, "Errore nel processare la notifica di $packageName", e)
            }
        }
    }

    companion object {
        private const val TAG = "ColfNotifListener"
    }
}

/**
 * Rimuove da [lastSentAtByKey] le entry il cui ultimo invio è più vecchio di
 * [windowMillis] rispetto a [now]: dopo la finestra di dedup quella entry non
 * può più far scattare [NotificationDeduplicator.isDuplicate], quindi
 * tenerla in memoria servirebbe solo a far crescere la mappa senza limiti.
 *
 * Funzione pura, senza dipendenze Android: testabile direttamente in JVM.
 */
internal fun pruneExpiredDedupEntries(
    lastSentAtByKey: MutableMap<String, Long>,
    now: Long,
    windowMillis: Long = NotificationDeduplicator.DEFAULT_WINDOW_MILLIS,
) {
    val iterator = lastSentAtByKey.entries.iterator()
    while (iterator.hasNext()) {
        val lastSentAt = iterator.next().value
        if (now - lastSentAt > windowMillis) {
            iterator.remove()
        }
    }
}
