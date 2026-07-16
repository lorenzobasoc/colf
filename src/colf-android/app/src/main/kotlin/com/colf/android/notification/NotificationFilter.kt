package com.colf.android.notification

/**
 * Filtro puro (nessun I/O, nessuna dipendenza Android) che decide se una
 * notifica bancaria "sembra" un pagamento da inoltrare al bot CoLF.
 *
 * Regola: la notifica deve contenere un importo (es. "42,50 EUR", "€12.34",
 * "EUR 30,00") E almeno una parola chiave di spesa, e NON deve contenere
 * parole chiave di entrata/accredito (che hanno priorità: uno stipendio con
 * un importo non va mai inoltrato anche se contenesse per assurdo una
 * keyword di spesa).
 */
object NotificationFilter {

    /** Parole chiave (case-insensitive) che indicano un pagamento in uscita. */
    val EXPENSE_KEYWORDS: List<String> = listOf(
        "pagamento",
        "pagato",
        "acquisto",
        "addebito",
        "speso",
        "spesa",
        "prelievo",
        "pos",
        "spent",
        "payment",
    )

    /** Parole chiave (case-insensitive) che indicano un'entrata: escludono sempre. */
    val INCOME_KEYWORDS: List<String> = listOf(
        "accredito",
        "bonifico ricevuto",
        "stipendio",
        "rimborso",
        "ricevuto",
        "entrata",
    )

    /**
     * Importo monetario: simbolo/valuta prima o dopo il numero.
     * Copre "42,50 EUR", "€12.34", "EUR 30,00", "12.345,67€".
     */
    private val AMOUNT_REGEX = Regex(
        """(?:€|EUR)\s?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?""" +
            """|\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?\s?(?:€|EUR)""",
        RegexOption.IGNORE_CASE,
    )

    fun isExpenseNotification(title: String?, text: String?): Boolean {
        val combined = "${title.orEmpty()} ${text.orEmpty()}".trim()
        if (combined.isBlank()) return false

        val lower = combined.lowercase()
        if (INCOME_KEYWORDS.any { lower.containsWord(it) }) return false
        if (!AMOUNT_REGEX.containsMatchIn(combined)) return false

        return EXPENSE_KEYWORDS.any { lower.containsWord(it) }
    }

    /** Contiene la keyword come parola/sequenza intera, non come sotto-stringa di un'altra parola. */
    private fun String.containsWord(keyword: String): Boolean {
        val escaped = Regex.escape(keyword)
        return Regex("""(?<![\p{L}\p{N}])$escaped(?![\p{L}\p{N}])""").containsMatchIn(this)
    }
}
