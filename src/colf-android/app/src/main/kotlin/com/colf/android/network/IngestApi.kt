package com.colf.android.network

import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

private val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()
private val json = Json { ignoreUnknownKeys = true }

/** Corpo della richiesta POST /ingest/notification: i @SerialName rispecchiano il contratto del server. */
@Serializable
data class NotificationPayload(
    @SerialName("package") val packageName: String,
    val title: String,
    val text: String,
    @SerialName("posted_at") val postedAt: String,
) {
    fun toJson(): String = json.encodeToString(this)
}

/** Esito di una singola chiamata di ingest, già classificato per la logica di retry del Worker. */
sealed class IngestResult {
    /** Presa in carico dal bot. */
    data object Ok : IngestResult()

    /** C'è già una spesa in sospeso sul bot: non ritentare. */
    data object Busy : IngestResult()

    /** Token errato: non ritentare. */
    data object Unauthorized : IngestResult()

    /** Payload rifiutato dal server: non ritentare. */
    data object BadRequest : IngestResult()

    /** Errore lato server (502 e simili): ritentare. */
    data object ServerError : IngestResult()

    /** Errore di rete/timeout, o il tunnel VPN non è ancora su: ritentare. */
    data class NetworkFailure(val cause: Throwable) : IngestResult()

    /** Risposta inattesa (status code non documentato): non ritentare, ma loggare. */
    data class Unexpected(val code: Int) : IngestResult()

    /** Base URL vuoto o senza schema http/https: errore di configurazione, non ritentare. */
    data class InvalidUrl(val cause: Throwable) : IngestResult()
}

sealed class HealthResult {
    data object Ok : HealthResult()
    data object Unauthorized : HealthResult()
    data class Unreachable(val cause: Throwable) : HealthResult()
    data class Unexpected(val code: Int) : HealthResult()

    /** Base URL vuoto o senza schema http/https: l'utente deve correggere il campo, non è un problema di rete. */
    data class InvalidUrl(val cause: Throwable) : HealthResult()
}

/** Client HTTP verso il server di ingest CoLF (raggiungibile solo via VPN, vedi README). */
class IngestApi(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build(),
) {

    suspend fun postNotification(baseUrl: String, token: String, payload: NotificationPayload): IngestResult {
        val request = try {
            Request.Builder()
                .url(joinUrl(baseUrl, "/ingest/notification"))
                .header("X-Ingest-Token", token)
                .post(payload.toJson().toRequestBody(JSON_MEDIA_TYPE))
                .build()
        } catch (e: IllegalArgumentException) {
            // Base URL vuoto o senza schema http/https: OkHttp lo rifiuta al momento
            // della build della Request, prima di qualunque I/O. Non è un errore di
            // rete: non va ritentato, altrimenti si sveglia la VPN all'infinito.
            return IngestResult.InvalidUrl(e)
        }

        val response = try {
            client.executeAsync(request)
        } catch (e: IOException) {
            return IngestResult.NetworkFailure(e)
        }

        response.use {
            return when (it.code) {
                200 -> IngestResult.Ok
                401 -> IngestResult.Unauthorized
                400 -> IngestResult.BadRequest
                409 -> IngestResult.Busy
                502 -> IngestResult.ServerError
                else -> IngestResult.Unexpected(it.code)
            }
        }
    }

    suspend fun health(baseUrl: String, token: String): HealthResult {
        val request = try {
            Request.Builder()
                .url(joinUrl(baseUrl, "/ingest/health"))
                .header("X-Ingest-Token", token)
                .get()
                .build()
        } catch (e: IllegalArgumentException) {
            // Vedi commento analogo in postNotification(): Base URL vuoto o senza
            // schema http/https, rifiutato da OkHttp prima di qualunque I/O.
            return HealthResult.InvalidUrl(e)
        }

        val response = try {
            client.executeAsync(request)
        } catch (e: IOException) {
            return HealthResult.Unreachable(e)
        }

        response.use {
            return when (it.code) {
                200 -> HealthResult.Ok
                401 -> HealthResult.Unauthorized
                else -> HealthResult.Unexpected(it.code)
            }
        }
    }

    private fun joinUrl(baseUrl: String, path: String): String {
        val trimmedBase = baseUrl.trimEnd('/')
        return "$trimmedBase$path"
    }
}

/** Adatta la callback OkHttp a una funzione sospendibile senza dipendenze extra. */
private suspend fun OkHttpClient.executeAsync(request: Request): Response =
    suspendCancellableCoroutine { continuation ->
        val call = newCall(request)
        continuation.invokeOnCancellation { call.cancel() }
        call.enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                if (!continuation.isCancelled) continuation.resumeWithException(e)
            }

            override fun onResponse(call: Call, response: Response) {
                continuation.resume(response)
            }
        })
    }
