# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Scopo del progetto

CoLF è un assistente personale controllato da Telegram. Copre due domini:

- **Spese** — l'utente scrive in chat un messaggio in linguaggio naturale (es. "spesa
  esselunga 42,50"), il bot lo categorizza con un LLM locale e lo inserisce nel
  Google Sheet dell'anno/mese corrente.
- **Fatture** — l'utente crea fatture elettroniche FatturaPA v1.2 (regime
  forfettario RF19) via Telegram o via web UI. L'API genera l'XML e lo invia al
  SdI via PEC. I dati clienti e le fatture sono persistiti su SQLite.

Il dominio è italiano: categorie, messaggi all'utente e nomi dei mesi sono in
italiano.

## Architettura tecnica

Il repo contiene due servizi separati, con dipendenze e Dockerfile distinti,
più un modulo client nativo (`src/colf-android`, senza Dockerfile, non parte
del deploy Docker).

### `src/colf` — API FastAPI

Package `colf`, layout a moduli per feature. Avvio in `app.py`: un `lifespan`
asincrono carica LLM, client Google Sheets e connessione SQLite in `app.state`.

- `config.py` — `Settings` (frozen dataclass) costruito da `.env` nella root del
  repo. `get_settings()` è cached con `lru_cache`. Contiene anche i dati fissi del
  cedente (CEDENTE_NOME, CEDENTE_PIVA, ecc.) e le credenziali PEC.
- `app.py` — registra i router di `expenses` e `invoices`; inizializza il DB SQLite
  nel `lifespan` (`aiosqlite.connect`, `create_tables`, `db.row_factory`).

#### Modulo `expenses/`

- `router.py` — `POST /api/agents/expenses/parse` e `POST /api/agents/expenses/commit`;
  `POST /api/agents/expenses/parse-notification` (spesa da notifica bancaria: importo
  ed esercente via regex, categoria via LLM) e `POST /api/agents/expenses/categorize`
  (ricalcolo categoria quando l'esercente non è estraibile e l'utente scrive la
  descrizione a mano).
- `service.py` — `parse_expense()` e `commit_expense()`.
- `llm/categorizer.py` — modello GGUF 1.5B con `llama-cpp-python`, temp 0.
- `llm/date_extractor.py` — estrazione data via LLM con few-shot dinamici.
- `sheets.py` — client `gspread`; `add_expense()` scrive sul Google Sheet.
- `text_parsing.py` — estrazione importo e descrizione via regex.
- `sharing.py` — logica pura spese condivise: trigger regex ("da dividere
  con…"), guardrail nomi LLM + fallback split, divisione `Decimal` (l'utente
  assorbe il resto), `append_debts` per accodare le righe nel blocco debitori
  (raggruppato per persona, nessuna somma).
- `llm/participants_extractor.py` — estrazione nomi partecipanti via LLM
  (few-shot, temp 0); l'output passa dal guardrail di `sharing.py`.
- `domain.py` / `schemas.py` / `constants.py` — entità, modelli Pydantic, costanti.

**Flusso spese:** messaggio → `parse_expense` (data LLM, importo/descrizione regex,
categoria LLM) → scheda conferma bot → conferma → `commit_expense` → Google Sheets.

**Spese condivise:** "Pizza 30 da dividere con Giulio e Bea" → il totale è
diviso per i partecipanti (utente incluso, `ROUND_HALF_UP`, l'utente assorbe
il resto); la quota utente va in A:D come spesa normale, i debitori vengono
accodati nel blocco `G25:I44` dello stesso foglio mensile, raggruppato per
persona: G=nome (una sola volta, sulla prima riga del gruppo), H=descrizione
della spesa, I=quota. Ogni spesa condivisa aggiunge, per ciascun debitore,
una nuova riga in fondo al gruppo di quella persona (nome vuoto nelle righe
successive alla prima) — nessuna somma/accumulo. La clausola va scritta in
fondo al messaggio. Se il blocco debitori fallisce dopo la riga spesa, il
bot avvisa (nessun rollback). Nel bot la scheda mostra totale/quote e il
bottone ✏️ Partecipanti (`edit:participants`; "nessuno" → spesa normale).

**Spese da notifica bancaria:** l'app Android (`src/colf-android/`) intercetta
la notifica di pagamento della banca e la inoltra al server di ingest del bot
(vedi sotto), che chiama `POST /api/agents/expenses/parse-notification` con
pacchetto/titolo/testo/timestamp della notifica; importo ed esercente sono
estratti via regex, la categoria via LLM. Il bot mostra la stessa scheda di
conferma del flusso testuale, con gli stessi bottoni. Se l'esercente non è
estraibile, la risposta ha `needs_description: true`: il bot chiede la
descrizione all'utente e ricalcola la categoria con
`POST /api/agents/expenses/categorize`. Il commit è lo stesso `commit_expense`
esistente, nessuna scrittura diversa su Google Sheets.

#### Modulo `invoices/`

- `constants.py` — `InvoiceStato` (StrEnum: BOZZA/INVIATA/CONSEGNATA/SCARTATA/PAGATA),
  `CAUSALI` (3 testi legali forfettario), `BOLLO_IMPORTO = Decimal("2.00")`,
  `FATTURA_NS`, `SDI_PEC`.
- `domain.py` — frozen dataclasses `Client` e `Invoice`.
- `schemas.py` — modelli Pydantic: `ClientCreate/Update/Response`, `InvoiceDraft`,
  `ParseInvoiceRequest/Response`, `CommitInvoiceResponse`, `InvoiceListItem/Response`.
- `dependencies.py` — `get_db(request)` legge `app.state.db`; `get_settings_dep`.
- `repository.py` — `create_tables()` (idempotente) + CRUD async con `aiosqlite`
  raw SQL. Importi salvati come TEXT. Tabelle: `clients`, `invoices`.
- `xml_builder.py` — `build_fattura_xml(invoice, client, settings) -> bytes` con
  `lxml`. **Namespace:** root `<p:FatturaElettronica xmlns:p="...">`, figli senza
  namespace (`elementFormDefault=unqualified`). `DatiBollo` presente nell'XML
  (BolloVirtuale=SI, ImportoBollo=2.00) ma **non sommato** al totale fattura
  (il bollo è versato separatamente via F24). `totale = importo`.
- `pec_sender.py` — `send_via_pec(xml_bytes, filename, settings)` async con
  `aiosmtplib`, TLS implicito. Destinatario: `sdi01@pec.fatturapa.it`.
- `service.py` — orchestrazione: `parse_invoice` (ricerca fuzzy cliente LIKE),
  `commit_invoice` (crea DB record, genera XML, salva file, invia PEC; se PEC
  fallisce rimane BOZZA ma XML è salvato), CRUD clienti, query scadenze.
- `router.py` — due `APIRouter`: `api_router` (prefix `/api`) per JSON API usata
  dal bot; `ui_router` (prefix `/ui`) per Jinja2 HTML.
- `templates/` — 5 template Jinja2 con Bootstrap 5 CDN: `base.html`,
  `invoices_list.html`, `invoice_new.html`, `clients_list.html`, `client_form.html`.

**Flusso fatture (bot):** `/fattura <nome>` → `POST /api/invoices/parse` (ricerca
cliente fuzzy, prefill template) → scheda conferma con tastiera inline → conferma →
`POST /api/invoices/commit` → XML generato + inviato PEC → riepilogo.

**Web UI:** `http://localhost:8000/ui/invoices` e `/ui/clients`.

**Progressivo invio:** `f"{anno}{numero:04d}"` es. `"20260001"`.
**Nome file XML:** `IT{PIVA_CEDENTE}_{ProgressivoInvio}.xml`.
**XML salvati in:** `settings.invoices_xml_dir` (default `data/invoices/xml/`).
**DB SQLite in:** `settings.sqlite_path` (default `data/colf.db`).

### `src/colf-telegram-bot` — bot Telegram

Servizio standalone (`python-telegram-bot`, polling). Non contiene logica di
dominio: chiama solo le API REST con `httpx.AsyncClient`.

- `telegram_bot.py` — handler per messaggi di testo (spese) e comandi fatture.
  Expense callbacks: `confirm`, `cancel`, `edit:*`, `cat:*`, `back`.
  Invoice callbacks: prefisso `inv_` (`inv_confirm`, `inv_cancel`, `inv_edit:*`,
  `inv_back`). Draft spese in `chat_data["draft"]`; draft fatture in
  `chat_data["invoice_draft"]`.
- `expense_card.py` — helper puri per scheda spesa (nessun I/O).
- `invoice_card.py` — helper puri per scheda fattura: `format_invoice_card`,
  `invoice_main_keyboard`, `invoice_back_keyboard`, `INV_FIELD_PROMPTS`.

**Comandi bot:** testo libero → spesa; `/fattura <nome>` → fattura; `/clienti` →
lista clienti; `/scadenze` → fatture in scadenza 7gg; `/stato <numero>` → stato
fattura; `/notifiche on|off|stato` → attiva/disattiva/mostra lo stato della
cattura spese da notifica bancaria.

**Server di ingest (notifiche bancarie):** il bot espone, nello stesso processo
che fa polling su Telegram, un piccolo server HTTP `aiohttp` per ricevere le
notifiche inoltrate dall'app Android. `POST /ingest/notification` (header
`X-Ingest-Token`, body `{"package","title","text","posted_at"}`) → `200
{"status":"ok"}`, `200 {"status":"disabled"}` se la feature è OFF, `401` token
errato, `400` payload invalido, `409 {"status":"busy"}` se c'è già una
spesa/fattura in sospeso, `502` se l'API non risponde. `GET /ingest/health`
(stesso token) → `{"status":"ok","enabled":true|false}`. Il toggle
`/notifiche` è **in memoria** nel bot, default **OFF**: va riattivato a ogni
riavvio del container. A feature OFF le notifiche in arrivo vengono scartate
silenziosamente (solo log). Il server non parte se mancano `INGEST_TOKEN` o
`TELEGRAM_CHAT_ID` (il bot continua comunque a funzionare normalmente).

### `src/colf-android` — app Android

App nativa Kotlin, installata sul telefono dell'utente. Non fa parte del
deploy Docker (nessun Dockerfile, nessun servizio nel compose). Compiti:

1. intercetta con un `NotificationListenerService` le notifiche di pagamento
   della banca configurata;
2. accende il tunnel WireGuard mandando l'intent
   `com.wireguard.android.action.SET_TUNNEL_UP` all'app WireGuard ufficiale
   (richiede "Allow remote control intents" abilitato in WireGuard);
3. fa `POST` della notifica (pacchetto, titolo, testo, timestamp) al server di
   ingest del bot Telegram (vedi sopra), con `X-Ingest-Token` come credenziale.

### Configurazione

`.env` nella root del repo — variabili richieste:

```
# Esistenti
LLM_NAME=qwen2.5-1.5b-instruct-q4_k_m.gguf
SERVICE_ACCOUNT_PATH=.keys/sheets_mcp_service_account.json

# Nuove (invoices)
CEDENTE_NOME=LORENZO
CEDENTE_COGNOME=BASOC
CEDENTE_PIVA=03065470308
CEDENTE_CF=BSCLNZ01P09Z140F
CEDENTE_INDIRIZZO=VIA CAPOLUOGO 17
CEDENTE_CAP=33010
CEDENTE_COMUNE=LUSEVERA
CEDENTE_PROVINCIA=UD
CEDENTE_IBAN=IT37O0306964212100000006365
PEC_HOST=...
PEC_PORT=465
PEC_USER=...
PEC_PASSWORD=...
# Opzionali (hanno default):
SQLITE_PATH=data/colf.db
INVOICES_XML_DIR=data/invoices/xml
```

Il modello GGUF va in `src/colf/models/` (gitignored). Le credenziali Google
sono in `.keys/` (gitignored).

Il servizio `telegram-bot` usa inoltre queste variabili, per il server di
ingest delle notifiche bancarie (vedi sopra):

```
INGEST_TOKEN=...       # segreto condiviso con l'app Android; se manca il server di ingest non parte
TELEGRAM_CHAT_ID=...   # chat a cui mandare la scheda spesa generata da una notifica; se manca il server di ingest non parte
# Opzionale (ha default):
INGEST_PORT=8080
```

## Comandi

API in locale:

```bash
cd src && uv run uvicorn colf.app:app --reload
```

Bot Telegram in locale:

```bash
cd src/colf-telegram-bot && uv sync && uv run python run.py
```

Nota: eseguire con `src/` come working directory (il package `colf` non è installato).

Test:

```bash
cd src && uv run pytest tests/ -v                      # API
cd src/colf-telegram-bot && uv run pytest tests/ -v    # bot
```

## Deploy (`.docker/`)

`docker-compose.yml` definisce due servizi: `colf` (API, porta host 9901) e
`telegram-bot` (bot Telegram + server di ingest notifiche bancarie, porta
host 9902). Il DB SQLite è montato come volume `../data:/app/data` per
persistere tra i rebuild. Il modello GGUF è montato da `../models`.

`.docker/.env` (gitignored) contiene `TELEGRAM_BOT_TOKEN`, `INGEST_TOKEN`,
`TELEGRAM_CHAT_ID` e tutte le variabili cedente/PEC. `SQLITE_PATH` e
`INVOICES_XML_DIR` sono impostati esplicitamente nell'environment del compose
a `/app/data/colf.db` e `/app/data/invoices/xml`; `INGEST_PORT` è impostato a
`8080` (porta interna del container, esposta come 9902 sull'host).

```bash
cd .docker && docker compose up -d --build
```

`deploy.sh` fa il deploy su Raspberry Pi via rsync + docker compose. La build di
`llama-cpp-python` su ARM richiede 10-20 min. Il modello viene trasferito una
volta sola a mano.

```bash
cd .docker && ./deploy.sh
```

### Infrastruttura Raspberry Pi (host di produzione)

- Raspberry Pi 4, Raspberry Pi OS 64-bit (Debian trixie). Hostname `pi`, utente
  SSH `pi`. IP LAN `192.168.1.147` (WiFi, statico via nmcli).
- Girano su questo host: Pi-hole v6, Docker (con i container di CoLF) e
  Portainer CE per la gestione dei container.
- Portainer avviato con `-p 9443:9443 -p 8000:8000`, volume `portainer_data`,
  `-v /var/run/docker.sock`, `--restart=always`. Serve solo HTTPS su 9443
  (`https://192.168.1.147:9443` da LAN).

**Accesso remoto (VPN WireGuard):** hub su VPS Oracle (`158.180.229.217`,
IP VPN `10.0.0.1`), peer Mac (`10.0.0.5`) e telefono (`10.0.0.4`). Rete VPN
`10.0.0.0/24`, IP VPN del Pi `10.0.0.2`. Rete di casa è un hotspot mobile
WebCube (SIM Huawei, dietro CGNAT), con latenza alta e variabile
(100-475 ms) e PMTU discovery inaffidabile.

**Nota MTU:** su questa rete il default MTU del tunnel WireGuard causa
timeout per servizi che rispondono con pacchetti grandi (es. Portainer UI
su `https://10.0.0.2:9443` — TLS handshake ok, ma la UI completa va in
timeout mentre risposte piccole passano). Fix: impostare `MTU = 1280` nella
sezione `[Interface]` della config WireGuard del client (es. Mac), poi
riavviare il tunnel. Se serve, salire per gradini (1360, 1380) cercando il
massimo stabile. Diagnosi: `ping -D -s <n> 10.0.0.2` da un peer VPN — se
fallisce con pacchetti grandi ma passa con quelli piccoli, è MTU/MSS
clamping sul tunnel, non un problema applicativo.
