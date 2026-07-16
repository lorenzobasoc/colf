package com.colf.android.notification

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Regressione per il fix minore sulla mappa di dedup del service: le entry
 * più vecchie della finestra di dedup vanno rimosse a ogni inserimento,
 * altrimenti la mappa cresce senza limiti per tutta la vita del processo.
 * `pruneExpiredDedupEntries` è una funzione pura (nessuna dipendenza
 * Android), testabile senza istanziare il NotificationListenerService.
 */
class DedupStorePruningTest {

    @Test
    fun `rimuove le entry piu' vecchie della finestra di dedup`() {
        val map = mutableMapOf(
            "expired" to 0L,
            "fresh" to 970_000L,
        )

        pruneExpiredDedupEntries(map, now = 1_000_000L, windowMillis = 60_000L)

        assertFalse(map.containsKey("expired"))
        assertTrue(map.containsKey("fresh"))
        assertEquals(1, map.size)
    }

    @Test
    fun `entry esattamente al limite della finestra non viene rimossa`() {
        val map = mutableMapOf("key" to 1_000L)

        pruneExpiredDedupEntries(map, now = 1_000L + 60_000L, windowMillis = 60_000L)

        assertTrue(map.containsKey("key"))
    }

    @Test
    fun `entry appena oltre la finestra viene rimossa`() {
        val map = mutableMapOf("key" to 1_000L)

        pruneExpiredDedupEntries(map, now = 1_000L + 60_001L, windowMillis = 60_000L)

        assertFalse(map.containsKey("key"))
    }

    @Test
    fun `mappa vuota resta vuota`() {
        val map = mutableMapOf<String, Long>()

        pruneExpiredDedupEntries(map, now = 1_000L, windowMillis = 60_000L)

        assertTrue(map.isEmpty())
    }

    @Test
    fun `usa la finestra di default del deduplicator quando non specificata`() {
        val map = mutableMapOf("key" to 0L)

        pruneExpiredDedupEntries(map, now = NotificationDeduplicator.DEFAULT_WINDOW_MILLIS + 1)

        assertFalse(map.containsKey("key"))
    }
}
