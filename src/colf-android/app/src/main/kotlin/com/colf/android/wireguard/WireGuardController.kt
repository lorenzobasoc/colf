package com.colf.android.wireguard

import android.content.Context
import android.content.Intent
import android.util.Log

/**
 * Accende il tunnel WireGuard mandando un broadcast intent all'app
 * WireGuard ufficiale (com.wireguard.android), che deve avere "Allow remote
 * control intents" abilitato nelle sue impostazioni (vedi README).
 *
 * L'app WireGuard non espone un modo pubblico e affidabile per interrogare
 * lo stato del tunnel da un'altra app: non possiamo sapere con certezza se
 * il tunnel è già su prima di mandare l'intent. Per questo lo mandiamo
 * sempre prima di un tentativo di invio (portare su un tunnel già attivo è
 * un'operazione idempotente, non ha effetti collaterali) e il segnale reale
 * che il tunnel è pronto è che la richiesta HTTP successiva vada a buon
 * fine — da cui il retry a backoff nel Worker.
 */
object WireGuardController {

    private const val TAG = "WireGuardController"
    private const val WIREGUARD_PACKAGE = "com.wireguard.android"
    private const val ACTION_SET_TUNNEL_UP = "com.wireguard.android.action.SET_TUNNEL_UP"
    private const val EXTRA_TUNNEL = "tunnel"

    fun bringTunnelUp(context: Context, tunnelName: String) {
        if (tunnelName.isBlank()) {
            Log.w(TAG, "Nessun nome tunnel configurato: salto l'intent a WireGuard")
            return
        }
        val intent = Intent(ACTION_SET_TUNNEL_UP).apply {
            setPackage(WIREGUARD_PACKAGE)
            putExtra(EXTRA_TUNNEL, tunnelName)
        }
        try {
            context.sendBroadcast(intent)
            Log.d(TAG, "Inviato SET_TUNNEL_UP per il tunnel '$tunnelName'")
        } catch (e: Exception) {
            // L'app WireGuard potrebbe non essere installata: non è un errore fatale,
            // il retry a backoff sulla POST gestirà comunque l'assenza di rete.
            Log.w(TAG, "Impossibile inviare l'intent a WireGuard (app non installata?)", e)
        }
    }
}
