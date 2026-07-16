package com.colf.android.notification

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NotificationDeduplicatorTest {

    @Test
    fun `prima notifica per una chiave non e' mai un duplicato`() {
        val isDuplicate = NotificationDeduplicator.isDuplicate(
            key = "pkg|title|text",
            timestampMillis = 1_000L,
            lastSentAtByKey = emptyMap(),
        )
        assertFalse(isDuplicate)
    }

    @Test
    fun `stessa notifica entro 60s dall'ultimo invio e' un duplicato`() {
        val isDuplicate = NotificationDeduplicator.isDuplicate(
            key = "pkg|title|text",
            timestampMillis = 1_000L + 30_000L,
            lastSentAtByKey = mapOf("pkg|title|text" to 1_000L),
        )
        assertTrue(isDuplicate)
    }

    @Test
    fun `stessa notifica esattamente al limite della finestra e' un duplicato`() {
        val isDuplicate = NotificationDeduplicator.isDuplicate(
            key = "pkg|title|text",
            timestampMillis = 1_000L + NotificationDeduplicator.DEFAULT_WINDOW_MILLIS,
            lastSentAtByKey = mapOf("pkg|title|text" to 1_000L),
        )
        assertTrue(isDuplicate)
    }

    @Test
    fun `stessa notifica oltre 60s dall'ultimo invio non e' un duplicato`() {
        val isDuplicate = NotificationDeduplicator.isDuplicate(
            key = "pkg|title|text",
            timestampMillis = 1_000L + 60_001L,
            lastSentAtByKey = mapOf("pkg|title|text" to 1_000L),
        )
        assertFalse(isDuplicate)
    }

    @Test
    fun `chiavi diverse non interferiscono tra loro`() {
        val isDuplicate = NotificationDeduplicator.isDuplicate(
            key = "pkg|other-title|text",
            timestampMillis = 1_030L,
            lastSentAtByKey = mapOf("pkg|title|text" to 1_000L),
        )
        assertFalse(isDuplicate)
    }

    @Test
    fun `keyFor produce chiavi diverse per package, title o text diversi`() {
        val base = NotificationDeduplicator.keyFor("com.bank.app", "Pagamento", "42,50 EUR")
        val differentPackage = NotificationDeduplicator.keyFor("com.other.app", "Pagamento", "42,50 EUR")
        val differentTitle = NotificationDeduplicator.keyFor("com.bank.app", "Addebito", "42,50 EUR")
        val differentText = NotificationDeduplicator.keyFor("com.bank.app", "Pagamento", "10,00 EUR")

        assertFalse(base == differentPackage)
        assertFalse(base == differentTitle)
        assertFalse(base == differentText)
        assertEquals(base, NotificationDeduplicator.keyFor("com.bank.app", "Pagamento", "42,50 EUR"))
    }
}
