package com.colf.android.notification

/**
 * Logica di deduplica isolata in funzioni pure e testabili: Android spesso
 * ripubblica la stessa notifica (stesso package+title+text) quando l'app
 * bancaria la aggiorna. Non vogliamo inoltrare due volte la stessa spesa se
 * arriva entro una finestra di tempo breve.
 *
 * Lo stato (ultimo invio per chiave) resta fuori da questo file, tenuto dal
 * chiamante (il Service): qui c'è solo la decisione, senza side effect.
 */
object NotificationDeduplicator {

    const val DEFAULT_WINDOW_MILLIS: Long = 60_000L

    /** Chiave di deduplica: stesso package + title + text. */
    fun keyFor(packageName: String, title: String?, text: String?): String =
        "$packageName|${title.orEmpty()}|${text.orEmpty()}"

    /**
     * True se [timestampMillis] è entro [windowMillis] dall'ultimo invio noto
     * per [key] in [lastSentAtByKey] (mappa chiave -> timestamp dell'ultimo
     * invio già effettuato). Timestamp precedenti al più recente (notifiche
     * fuori ordine) sono considerati comunque duplicati se nella finestra.
     */
    fun isDuplicate(
        key: String,
        timestampMillis: Long,
        lastSentAtByKey: Map<String, Long>,
        windowMillis: Long = DEFAULT_WINDOW_MILLIS,
    ): Boolean {
        val lastSentAt = lastSentAtByKey[key] ?: return false
        val delta = kotlin.math.abs(timestampMillis - lastSentAt)
        return delta <= windowMillis
    }
}
