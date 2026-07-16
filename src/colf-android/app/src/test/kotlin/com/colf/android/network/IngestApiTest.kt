package com.colf.android.network

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Regressione per il bug bloccante: un Base URL vuoto o senza schema
 * http/https fa lanciare IllegalArgumentException a OkHttp durante la build
 * della Request. Prima del fix questa eccezione risaliva non gestita fuori
 * da IngestApi (crash del processo in ConfigViewModel.testConnection(),
 * Worker marcato FAILED senza log chiaro in NotificationForwardWorker).
 *
 * Questi test non toccano la rete: la build della Request fallisce prima di
 * qualunque I/O, quindi runBlocking (senza un dispatcher/motore di test)
 * è sufficiente.
 */
class IngestApiTest {

    private val api = IngestApi()

    @Test
    fun `health con Base URL vuoto produce InvalidUrl invece di lanciare`() = runBlocking {
        val result = api.health(baseUrl = "", token = "tok")
        assertTrue("atteso HealthResult.InvalidUrl, ottenuto $result", result is HealthResult.InvalidUrl)
    }

    @Test
    fun `health con Base URL senza schema produce InvalidUrl invece di lanciare`() = runBlocking {
        val result = api.health(baseUrl = "10.0.0.2:9902", token = "tok")
        assertTrue("atteso HealthResult.InvalidUrl, ottenuto $result", result is HealthResult.InvalidUrl)
    }

    @Test
    fun `postNotification con Base URL vuoto produce InvalidUrl invece di lanciare`() = runBlocking {
        val payload = NotificationPayload(
            packageName = "com.bank.app",
            title = "Pagamento",
            text = "Pagamento di 42,50 EUR presso ESSELUNGA SPA",
            postedAt = "2026-07-14T12:33:00",
        )

        val result = api.postNotification(baseUrl = "", token = "tok", payload = payload)
        assertTrue("atteso IngestResult.InvalidUrl, ottenuto $result", result is IngestResult.InvalidUrl)
    }

    @Test
    fun `postNotification con Base URL senza schema produce InvalidUrl invece di lanciare`() = runBlocking {
        val payload = NotificationPayload(
            packageName = "com.bank.app",
            title = "Pagamento",
            text = "Pagamento di 42,50 EUR presso ESSELUNGA SPA",
            postedAt = "2026-07-14T12:33:00",
        )

        val result = api.postNotification(baseUrl = "10.0.0.2:9902", token = "tok", payload = payload)
        assertTrue("atteso IngestResult.InvalidUrl, ottenuto $result", result is IngestResult.InvalidUrl)
    }
}
