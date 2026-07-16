# colf-android

App Android nativa (Kotlin) che intercetta le notifiche di pagamento della
banca sul telefono del proprietario e le inoltra al bot CoLF, così una spesa
pagata con carta finisce nel Google Sheet senza doverla scrivere a mano in
chat.

Pensata per girare solo sul telefono del proprietario del server, con
permessi concessi a mano: non è un prodotto multi-utente.

## Cosa fa

1. Un `NotificationListenerService` osserva tutte le notifiche di sistema e
   scarta subito quelle che non arrivano da un package bancario configurato,
   quelle di gruppo/summary e quelle senza testo.
2. Le notifiche superstiti passano da un filtro puro
   (`NotificationFilter.isExpenseNotification`) che accetta solo notifiche
   con un importo (`42,50 EUR`, `€12.34`, `EUR 30,00`, ...) e una parola
   chiave di spesa (pagamento, pagato, acquisto, addebito, speso, spesa,
   prelievo, POS, spent, payment), rifiutando sempre le notifiche di
   entrata/accredito (accredito, bonifico ricevuto, stipendio, rimborso,
   ricevuto, entrata).
3. Notifiche identiche (stesso package + titolo + testo) ricevute entro 60
   secondi da una già inoltrata vengono scartate (dedup), perché Android
   spesso ripubblica la stessa notifica quando l'app bancaria la aggiorna.
4. Il lavoro di invio viene accodato a un `CoroutineWorker` di WorkManager,
   che:
   - manda un broadcast intent all'app WireGuard ufficiale per accendere il
     tunnel (`SET_TUNNEL_UP`);
   - prova a fare `POST /ingest/notification` con retry a backoff (2s, 4s,
     8s, 16s tra un tentativo e l'altro, 5 tentativi totali, nessuna attesa
     dopo l'ultimo) perché non c'è modo affidabile di sapere se il tunnel è
     già su — l'unico segnale reale è che la richiesta HTTP vada a buon fine;
   - se anche questi tentativi falliscono per motivi di rete o per un `502`,
     delega il retry a WorkManager stesso (`Result.retry()`), che riprova più
     avanti (con backoff esponenziale a partire da 30s) quando c'è di nuovo
     rete, anche se l'app nel frattempo è stata chiusa;
   - su `401`, `400`, `409`, `200 {"status":"disabled"}` o un Base URL vuoto/
     malformato (es. senza `http://`) si ferma subito e non ritenta (sono
     esiti definitivi, non transitori).
5. Una Activity Compose (Material 3) permette di configurare URL del server,
   token, nome del tunnel WireGuard e lista dei package bancari da
   ascoltare, con un pulsante "Testa connessione" e uno per aprire le
   impostazioni di accesso alle notifiche.

## Compilare e installare

Serve l'Android SDK (`compileSdk`/`targetSdk` 36, `minSdk` 26) e un JDK
recente (il progetto è stato sviluppato e verificato con Temurin 24; Gradle
8.14 + AGP 8.13.1 girano correttamente su quella JVM producendo bytecode
target 17, senza bisogno di installare un altro JDK).

```bash
cd src/colf-android
echo "sdk.dir=/percorso/del/tuo/Android/sdk" > local.properties   # non committato

./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Test unità (JVM, sulle funzioni pure di filtro/dedup):

```bash
./gradlew test
```

## Permessi e configurazioni da fare a mano

### 1. Accesso alle notifiche

Android non permette di richiedere l'accesso alle notifiche come permesso
runtime standard: va concesso a mano.

- Apri l'app, vai nella schermata di configurazione e tocca **"Apri
  impostazioni notifiche"** (oppure `Impostazioni > App > Accesso speciale
  alle app > Accesso alle notifiche` sul telefono), poi abilita **CoLF
  Notify**.
- Il pulsante **"Ricontrolla stato permesso"** aggiorna l'indicatore nella
  UI dopo essere tornati dalle impostazioni.

### 2. "Allow remote control intents" nell'app WireGuard ufficiale

L'app manda un broadcast intent (`com.wireguard.android.action.SET_TUNNEL_UP`,
extra `tunnel` = nome del tunnel) all'app **WireGuard ufficiale**
(`com.wireguard.android`, quella del Play Store/F-Droid) per accendere il
tunnel prima di contattare il server. Per impostazione predefinita WireGuard
ignora questi intent da app esterne: va abilitato esplicitamente.

- Apri l'app WireGuard → menu (⋮) in alto a destra → **Settings** →
  abilita **"Allow remote control intents"**.
- Senza questa opzione il broadcast viene inviato ma non ha alcun effetto:
  il tunnel non si accende e la POST fallirà finché non risali a mano.
- L'app CoLF Notify non può interrogare in modo affidabile lo stato del
  tunnel (WireGuard non espone un'API pubblica per questo): il broadcast
  viene sempre inviato prima di un tentativo di invio (è idempotente, non
  ha effetti collaterali se il tunnel è già su) e il retry a backoff copre
  il tempo che la VPN impiega a risalire.

### 3. Trovare il package name dell'app bancaria

Serve per popolare la lista "App bancarie da ascoltare" nella schermata di
configurazione (un package per riga). Modi rapidi:

- da un telefono con `adb` collegato:
  ```bash
  adb shell pm list packages | grep -i <nome banca>
  ```
- oppure, dallo store: apri la pagina dell'app sul Play Store da browser e
  guarda l'URL (`.../store/apps/details?id=it.bancaesempio.app`) — il
  parametro `id` è il package name.

### 4. Configurazione URL/token/tunnel

Nella schermata unica dell'app:

- **Base URL**: indirizzo del bot CoLF raggiungibile via VPN, es.
  `http://10.0.0.2:9902` (vedi `CLAUDE.md` del repo per l'IP VPN del Pi in
  uso).
- **Token**: valore condiviso con il server, mandato come header
  `X-Ingest-Token` su ogni richiesta.
- **Nome tunnel WireGuard**: deve corrispondere esattamente al nome del
  tunnel configurato nell'app WireGuard ufficiale sul telefono.
- **App bancarie**: un package per riga.
- **Abilita inoltro**: interruttore generale, se spento il Worker scarta
  subito le notifiche in coda senza contattare il server.
- **Testa connessione**: chiama `GET /ingest/health` con l'URL e il token
  correnti e mostra l'esito (ok / token errato / irraggiungibile / URL non
  valido / feature spenta lato bot).

### 5. Attivare la feature anche lato bot

Configurare l'app da sola non basta: il bot CoLF ha la feature di ingest
notifiche **spenta di default**. Va accesa mandando al bot Telegram il
comando:

```
/notifiche on
```

Se la feature è spenta lato bot, il server risponde `200
{"status":"disabled"}` e l'app non ritenta (non è un errore transitorio).

## Cleartext HTTP verso la VPN

Il server di ingest gira sul Raspberry Pi dietro la VPN WireGuard e non ha
TLS (è raggiungibile solo da chi è già sulla VPN). Invece di abilitare
`usesCleartextTraffic="true"` per l'intera app, `network_security_config.xml`
permette il cleartext solo verso gli host noti della VPN/LAN di casa
(`10.0.0.2`, `192.168.1.147`, `localhost`/`127.0.0.1` per test locali con
`adb reverse`): il traffico verso qualsiasi altro host resta vincolato a
HTTPS. Se l'IP VPN del server cambia, va aggiornato
`app/src/main/res/xml/network_security_config.xml` e ricompilata l'app (il
campo "Base URL" nella UI può puntare a un host diverso, ma se quell'host
non è in questa lista la richiesta cleartext verrà bloccata dal sistema).

## Struttura del progetto

```
app/src/main/kotlin/com/colf/android/
  notification/  NotificationFilter, NotificationDeduplicator (pure, testate),
                 ColfNotificationListenerService
  work/          NotificationForwardWorker (CoroutineWorker, retry a backoff)
  network/       IngestApi (OkHttp + kotlinx.serialization)
  wireguard/      WireGuardController (broadcast intent SET_TUNNEL_UP)
  data/          AppSettings, SettingsRepository (DataStore Preferences)
  ui/            MainActivity, ConfigScreen, ConfigViewModel (Compose, Material 3)
app/src/test/kotlin/com/colf/android/notification/
  NotificationFilterTest, NotificationDeduplicatorTest
```

## Contratto del server (per riferimento)

`POST /ingest/notification` — header `X-Ingest-Token: <token>`:

```json
{"package": "com.bank.app", "title": "Pagamento carta", "text": "Pagamento di 42,50 EUR presso ESSELUNGA SPA", "posted_at": "2026-07-14T12:33:00"}
```

Risposte: `200 {"status":"ok"}` (presa in carico), `200
{"status":"disabled"}` (feature spenta lato bot, non ritentare), `401`
(token errato, non ritentare), `400` (payload invalido, non ritentare), `409
{"status":"busy"}` (spesa già in sospeso, non ritentare), `502` (errore
server, ritentare).

`GET /ingest/health` — stesso header → `200 {"status":"ok","enabled":true|false}`.
