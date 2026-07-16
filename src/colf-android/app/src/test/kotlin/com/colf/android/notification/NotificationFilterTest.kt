package com.colf.android.notification

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NotificationFilterTest {

    // --- Casi positivi: pagamenti con importo riconoscibile ---

    @Test
    fun `pagamento con carta e importo in euro viene accettato`() {
        assertTrue(
            NotificationFilter.isExpenseNotification(
                title = "Pagamento carta",
                text = "Pagamento di 42,50 EUR presso ESSELUNGA SPA",
            ),
        )
    }

    @Test
    fun `acquisto POS con simbolo euro prima del numero viene accettato`() {
        assertTrue(
            NotificationFilter.isExpenseNotification(
                title = "Transazione POS",
                text = "Acquisto POS di €12.34 su AMAZON",
            ),
        )
    }

    @Test
    fun `addebito con EUR prima del numero viene accettato`() {
        assertTrue(
            NotificationFilter.isExpenseNotification(
                title = "Addebito",
                text = "Addebito di EUR 30,00 su carta prepagata",
            ),
        )
    }

    @Test
    fun `prelievo bancomat viene accettato`() {
        assertTrue(
            NotificationFilter.isExpenseNotification(
                title = "Prelievo",
                text = "Prelievo di 100,00 EUR da ATM",
            ),
        )
    }

    @Test
    fun `notifica in inglese con payment e spent viene accettata`() {
        assertTrue(
            NotificationFilter.isExpenseNotification(
                title = "Payment sent",
                text = "You spent 9.99 EUR at NETFLIX",
            ),
        )
    }

    @Test
    fun `importo con migliaia viene accettato`() {
        assertTrue(
            NotificationFilter.isExpenseNotification(
                title = "Pagamento",
                text = "Pagamento di 1.234,56 EUR presso CONCESSIONARIA",
            ),
        )
    }

    // --- Casi negativi: entrate/accrediti, sempre esclusi anche con importo ---

    @Test
    fun `accredito stipendio viene rifiutato`() {
        assertFalse(
            NotificationFilter.isExpenseNotification(
                title = "Accredito",
                text = "Accredito stipendio di 1500,00 EUR",
            ),
        )
    }

    @Test
    fun `bonifico ricevuto viene rifiutato`() {
        assertFalse(
            NotificationFilter.isExpenseNotification(
                title = "Bonifico",
                text = "Bonifico ricevuto di 200,00 EUR da MARIO ROSSI",
            ),
        )
    }

    @Test
    fun `rimborso viene rifiutato`() {
        assertFalse(
            NotificationFilter.isExpenseNotification(
                title = "Rimborso",
                text = "Hai ricevuto un rimborso di 15,00 EUR",
            ),
        )
    }

    // --- Casi negativi: nessun importo o nessuna keyword di spesa ---

    @Test
    fun `notifica senza importo viene rifiutata`() {
        assertFalse(
            NotificationFilter.isExpenseNotification(
                title = "Pagamento effettuato",
                text = "Il pagamento è andato a buon fine",
            ),
        )
    }

    @Test
    fun `notifica promozionale della banca senza importo viene rifiutata`() {
        assertFalse(
            NotificationFilter.isExpenseNotification(
                title = "Novità",
                text = "Attiva la nuova carta CoLF e ricevi vantaggi esclusivi",
            ),
        )
    }

    @Test
    fun `importo presente ma senza keyword di spesa viene rifiutato`() {
        assertFalse(
            NotificationFilter.isExpenseNotification(
                title = "Saldo conto",
                text = "Il tuo saldo attuale è 1.200,00 EUR",
            ),
        )
    }

    @Test
    fun `titolo e testo nulli vengono rifiutati`() {
        assertFalse(NotificationFilter.isExpenseNotification(title = null, text = null))
    }

    @Test
    fun `keyword come sottostringa di un'altra parola non fa scattare il match`() {
        // "pos" non deve far scattare il match dentro "disposizione".
        assertFalse(
            NotificationFilter.isExpenseNotification(
                title = "Info",
                text = "Somma a tua disposizione: 50,00 EUR",
            ),
        )
    }
}
