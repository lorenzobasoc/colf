# Notion → Google Sheets sul VPS

## Pagina Notion

```text
9
Cena 130 B
711 130 B

10
Caffe 110 B
Tempio 100
```

La pagina appartiene al database Taccuini; non serve scrivere il mese. `B` finale divide al 50% con Bea.
Il mese/anno sono quelli del primo rilevamento nel fuso `SYNC_TIMEZONE` e restano
fissi nei retry. Un giorno futuro rispetto a oggi causa errore: svuotare le
spese del mese precedente prima del cambio mese, senza mescolare arretrati.
La proprietà **Select** `Valuta` della pagina è obbligatoria: opzioni THB, EUR,
ecc. Creare un piccolo database Notion (es. Taccuini) e spostare la pagina
delle spese al suo interno; aggiungere la proprietà Valuta e selezionare THB.
Le singole spese restano testo libero nel corpo della pagina, senza righe
database per ogni acquisto e senza intestazione Valuta nel testo. Cambiarla
vale per le nuove spese; spese già preparate conservano il cambio salvato.
Usare pagine diverse per valute miste; gli ID si elencano separati da virgola.

Colf aggiunge ` ✅` alla singola riga dopo il commit su Google. Le righe già
marcate al primo avvio si considerano gestite. Puoi cancellare le righe o i
blocchi importati; se rimangono spese da importare, conservare il loro giorno e
la proprietà Valuta. Non modificare acquisti importati per correggere il foglio:
le correzioni contabili si effettuano manualmente.

Per nuove spese usare nuovi paragrafi Notion. Gli a capo nello stesso paragrafo
sono supportati, ma sostituire una riga importata con un nuovo acquisto nello
stesso blocco può essere indistinguibile da una modifica. Il worker si ferma
quando riconosce questa ambiguità, incluso un tick rimosso dopo conferma locale.
Non rimuovere i tick dalle spese che vuoi conservare in Notion. La cancellazione
di altre righe non cambia l'identità di una spesa. Se cancelli un'intera pagina,
rimuoverne anche l'ID dalla configurazione.

## Importi e layout

Cambio di riferimento storico ECB via Frankfurter, ultimo disponibile entro
sette giorni dalla data della spesa, mai futuro. EUR usa tasso 1. Non è il cambio
effettivo della carta. Valuta non supportata o rete non disponibile: nessuna
scrittura per la pagina interessata.

Gli importi vengono convertiti e arrotondati al multiplo di **0,05 EUR** più
vicino (`ROUND_HALF_UP` per i pareggi). Con B si divide prima il valore convertito
e si arrotonda la singola metà: la quota personale e quella Bea sono uguali.
L'approssimazione può cambiare la somma rispetto al cambio esatto; importi molto
piccoli possono arrotondarsi a zero. Non si fa un arrotondamento intermedio ai
centesimi. Esempi: 1,73 → 1,75; 1,46 → 1,45; 1,33 → 1,35.

A:D conserva giorno, descrizione, categoria Colf e quota personale; una spesa
non condivisa contiene il totale arrotondato. G23:H contiene solo le quote Bea,
sempre appese in coda allo storico esistente. Stesso giorno dell'ultimo gruppo:
append delle sole spese; giorno diverso: riga vuota e nuova intestazione giorno.
Valori numerici con il formato contabile euro esatto ereditato dalla colonna D
del foglio mensile, inclusa la spaziatura del simbolo. Allineamento a destra.
Solo se manca un formato euro di riferimento si usa `#,##0.00" €"`. Nessun riordino o riscrittura di vecchie celle.

G23:I deve essere vuoto o già nel nuovo formato. Prima migrare manualmente gli
eventuali vecchi debitori G25:I44; Colf non li cancella. Disattivare gli altri
scrittori di spese e i reminder debitori che usano il vecchio layout su questo
spreadsheet. Non occorre fermare le funzionalità fatture indipendenti.

## Accessi e installazione

1. Creare un'integrazione Notion con lettura e aggiornamento contenuti, e
   collegarla soltanto alle pagine richieste tramite il menu Connessioni.
2. Condividere il Google Sheet con il service account esistente come editor.
   Configurare ID spreadsheet per anno; i tab mensili italiani devono esistere.
3. La classificazione usa esplicitamente Haiku 5.5 (`claude-haiku-5-5`), senza
   fallback automatico ad altri modelli. Sul VPS Linux installare Python >=3.13 e Claude Code originale. Copiare il
   repository in `/opt/colf`, creare utente `colf` con home `/var/lib/colf` e
   rendere quella home scrivibile all'utente. Eseguire il login ufficiale
   `claude auth login` come utente `colf`. Controllare `claude auth status`:
   authMethod deve essere `claude.ai`. Non copiare token di sessione a mano.
4. Il worker non richiede llama.cpp: nella sua venv bastano `gspread>=6.2.1`,
   `google-auth>=2.36.0` e `python-dotenv>=1.0.0`. Con una venv dedicata:

   ```sh
   cd /opt/colf
   python3 -m venv .venv
   .venv/bin/pip install 'gspread>=6.2.1' 'google-auth>=2.36.0' 'python-dotenv>=1.0.0'
   ```

   Per sviluppare con l'ambiente completo esistente usare i comandi test sotto.
5. Copiare `deploy/notion-sync.env.example` in `/etc/colf/notion-sync.env`,
   impostare token Notion, ID pagine, file service account, spreadsheet e fuso.
   Usare il percorso assoluto reale del binario Claude, leggibile/eseguibile
   dall'utente `colf`. Credenziali leggibili solo da root/colf.
6. Il comando deve ereditare queste variabili (o caricarle da `.env` nella working
   directory). Prima provarlo su copie della pagina e del foglio:

   ```sh
   PYTHONPATH=src .venv/bin/python -m colf.notion_sync.run --dry-run
   PYTHONPATH=src .venv/bin/python -m colf.notion_sync.run
   ```

   Dry-run legge Notion/Google e può consumare l'abbonamento Claude; non modifica
   dati remoti o journal persistente (crea solo il lock locale). L'anteprima
   riporta data, categoria, tasso, importi e quote. Ripetere l'importazione:
   nessun nuovo addebito contabile e nessuna classificazione sulle righe gestite.
7. Dopo la prova copiare service/timer in `/etc/systemd/system`, poi:

   ```sh
   sudo systemctl daemon-reload
   sudo systemctl enable --now colf-notion-sync.timer
   systemctl list-timers colf-notion-sync.timer
   journalctl -u colf-notion-sync.service
   ```

Il timer controlla alle :00 e :30. È one-shot con lock: niente run sovrapposti.
La configurazione predefinita è per `/opt/colf`; adattare i percorsi se diverso.
Nessun timer viene attivato da questa implementazione nel workspace locale.

## Ripristino e limiti

Fare backup di `/var/lib/colf/notion-sync.db` con il timer fermo (o SQLite backup)
insieme al foglio. Non eliminare né modificare `_colf_imports`, il tab nascosto
che viene scritto atomicamente insieme ai due blocchi contabili. Se manca la
continuità del journal, il worker si ferma anziché reinserire righe già registrate:
ripristinare un backup coerente prima di proseguire.

Errore nel tick dopo commit Google: il controllo successivo riprova solo Notion.
Risposta Google persa: non si ritenta alla cieca, il controllo successivo legge
il registro. Limiti Claude/login scaduto lasciano le spese in attesa. Evitare
modifiche alla pagina durante l'importazione: Notion non offre una transazione
atomica con Google né un compare-and-swap; il worker rilegge prima del tick,
ma non può eliminare la gara fra quella lettura e l'aggiornamento.

I tick Notion sono confermati localmente dopo la risposta: se il server salva
un tick e la risposta va persa, è possibile recuperarlo dalla lettura seguente.
Se una riga identica viene cancellata e ricreata nello stesso blocco tra due
controlli, senza un'osservazione intermedia, il testo non fornisce identità
sufficiente: usare nuovi paragrafi per nuovi acquisti. Conservare anche spese
identiche reali in blocchi distinti è il modo più semplice di evitare ambiguità.

## Verifica locale

```sh
.venv/bin/python -m pytest src/tests -q
PYTHONPATH=src .venv/bin/python -m colf.notion_sync.run --help
```

Le API Notion e Google richiedono la prova su copie reali prima di attivare il
timer. I test automatici simulano i servizi esterni; non provano i permessi reali.

## Stato installazione VPS — 2026-11-10

Host SSH `develop`, utente servizio `colf`, codice in `/opt/colf`, home e stato
in `/var/lib/colf`, configurazione in `/etc/colf/notion-sync.env`. Installati
Python 3.13.18 e Claude Code 2.1.322. Service/timer validati con systemd-analyze;
timer ogni :00/:30 installato ma disabilitato in attesa degli accessi personali.

Accesso Google verificato dal VPS in sola lettura, intestazioni principali
compatibili (tollerato spazio iniziale in Importo) e blocco Bea di novembre
vuoto. Nessuna spesa inserita né modificata. Test worker sul VPS dopo gli aggiornamenti: 38 passed.

Passaggi utente ancora necessari:

1. Creare connessione interna Notion Colf con Read/Update content e aggiungerla
   alla pagina spese. Usare una pagina interna a un database, aggiungere la
   proprietà Select `Valuta` e scegliere THB.
2. Collegarsi con `develop`, eseguire `sudo nano /etc/colf/notion-sync.env` e
   valorizzare NOTION_TOKEN senza pubblicarlo in chat. Comunicare il link della
   pagina per configurare NOTION_PAGE_IDS.
3. Eseguire `sudo -iu colf /var/lib/colf/.local/bin/claude auth login` e completare
   l'accesso browser con il proprio abbonamento.

Poi verificare dry-run Notion/Google, controllare anteprima e avviare timer.

## Attivazione completata — 2026-11-10

La pagina `4140239f74f98077aa9ee6c654e8f021` ora appartiene a una data source
Notion e ha proprietà Select Valuta=THB. Login Claude Pro e accessi Notion/Google
verificati sul VPS. Modello Haiku 5.5 esplicito con regole 711=Cibo,
attrazioni/biglietti visite=Eventi, benzina/benza/transfer/aerei=Trasporti.

Prima importazione eseguita: sei spese, sei tick verificati in Notion, sei record
nel ledger, quote personali numeriche EUR con categorie emoji e sei quote Bea
in coda da G23. Seconda esecuzione senza nuove spese e senza duplicati.
Timer `colf-notion-sync.timer` abilitato e attivo, esecuzioni ogni :00 e :30.
Verifiche effettuate in lettura sul risultato dopo il commit.

## Arrotondamento aggiornato — 2026-11-10

Arrotondamento richiesto: passi di 0,05 EUR (5 centesimi), simbolo euro e
allineamento a destra. La precedente interpretazione a 0,50 EUR è stata corretta.
Le sei spese iniziali erano state cancellate manualmente dall'utente, insieme
alle quote Bea e ai tick: su richiesta esplicita sono state predisposte per il
retry, conservando gli stessi ID, date, cambi e categorie, aggiornando soltanto
le quote e ripristinando l'idempotenza dopo il reinserimento. Backup precedente
nel percorso `/var/lib/colf/backups/rounding-*` sul VPS.

Correzione finale dei sei importi e delle quote Bea: 1,75 / 1,75 / 1,45 / 1,20 /
1,35 / 1,35 EUR. Il job manuale viene rilanciato preservando gli ID del registro.
Backup prima della correzione sotto `/var/lib/colf/backups/five-cents-*`.

## Formato contabile originale preservato

La differenza visuale era causata dal formato CURRENCY generico che sostituiva
il formato NUMBER contabile personalizzato del foglio. I nuovi inserimenti
leggono il formato della precedente cella D e lo applicano ai nuovi importi,
con allineamento a destra; non cambiano font, bordi o importi esistenti.
Le dodici celle delle sei spese e quote Bea sono state corrette con il formato
originale di D43 e verificate tramite API: pattern identico, spaziatura
contabile ripristinata, valori numerici e registro invariati.
