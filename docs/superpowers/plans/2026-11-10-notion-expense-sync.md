# Notion Expense Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Importare spese testuali Notion nel Google Sheet Colf, convertire in
EUR e aggiungere ✅ senza duplicati dopo errori o riavvii.

**Architecture:** Timer systemd ogni 30 minuti, worker one-shot con lock.
Claude Code con abbonamento per categorie; calcoli deterministici. Journal
SQLite e registro Google per recupero; commit contabile Google atomico seguito
da tick Notion ripetibile.

**Tech Stack:** Python >=3.13, stdlib, gspread/google-auth/python-dotenv esistenti,
pytest e Claude Code CLI originale.

**Spec:** `docs/superpowers/specs/2026-11-10-notion-expense-sync-design.md`

## Global Constraints

- Nessun mese esplicito; mese/anno al primo rilevamento nel fuso configurato.
- Valuta nella proprietà Select della pagina; B significa metà con Bea.
- A:D conserva regole local-llm; G23:H nuovo layout per quota Bea.
- EUR numerici, multipli di 0,05 con due decimali e simbolo €, ROUND_HALF_UP; nessun importo deciso da Claude.
- Cancellazioni manuali consentite; tick dopo commit Google.
- Nessuna chiave API Claude, nessun LLM locale nel worker.
- Nessun attivatore produzione o scrittura dati reali durante l'implementazione.

## Review Focus

1. Risposta Google persa e tick fallito: registro impedisce doppie scritture.
2. Modifica di righe registrate o sostituzione identica: conflitto esplicito.
3. Journal perso: arresto, non ricreazione casuale di identità già importate.
4. Centesimi dispari, cambio storico, attraversamento mese/anno nei retry.
5. Layout vecchio debitori e più writer: nessuna sovrascrittura silenziosa.

## Task 1: Parser sorgente

Files: `src/colf/notion_sync/{__init__,model}.py`,
`src/tests/test_notion_sync_parser.py`.
Interfaces: `SourceLine`, `SourceExpense`, `parse_page(page_id, lines, *, today)`.

- [x] Test prima dell'implementazione e run rosso: modulo assente.
- [x] Parser valuta/giorno/descrizione/importo/B/tick con Decimal.
- [x] Identità sopravvive alla cancellazione di righe estranee; duplicati distinti.
- [x] Casi invalidi e numerici come `711`; suite verde.

## Task 2: Lettura Notion e tick

Files: `notion_sync/{http,notion}.py`, `src/tests/test_notion_sync_clients.py`.
Interfaces: `Notion.read_page`, `Notion.mark_imported`, `json_client`.

- [x] Test prima dell'implementazione e run rosso.
- [x] Paginazione, lettura ricorsiva, paragrafi/liste/heading testuali.
- [x] PATCH tick senza appiattire rich text, con rilettura e confronto blocco.
- [x] Test cambio concorrente di giorno o importo, paginazione e formattazione.
- [ ] Fixture anonimizzata della pagina Notion reale e prova permessi.

## Task 3: Cambio e Claude

Files: `notion_sync/{conversion,claude}.py`, medesimo test client.
Interfaces: `Rate`, `get_rate`, `split_eur`, `classify`.

- [x] Test prima dell'implementazione; euro, cambio storico valido/invalido,
  quote 1,75/1,76 per totale fittizio 3,51, categoria ammessa e ID completi.
- [x] Controllo login claude.ai; rifiuto configurazione API; strumenti disabilitati.
- [x] Endpoint Frankfurter verificato con richiesta pubblica e output reale.
- [x] Smoke classificazione reale con abbonamento: Cena → Cibo fuori.

## Task 4: Commit Google e registro

Files: `notion_sync/sheets.py`, `src/tests/test_notion_sync_sheets.py`.
Interfaces: `SheetStore.load_imports`, `SheetStore.commit_imports`, `bea_rows`.

- [x] Test rosso prima del codice, poi verde.
- [x] Singola batchUpdate: tabella principale, quote Bea e ledger nascosto.
- [x] Formati numerici, controllo intestazioni/layout legacy, crescita griglia.
- [x] Nessun retry cieco per mutazioni; registro con originali, cambio e quote.
- [ ] Validazione batchUpdate su copia reale del Google Sheet.

## Task 5: Worker e rilascio

Files: `notion_sync/run.py`, `src/tests/test_notion_sync_run.py`,
`deploy/colf-notion-sync.{service,timer}`, `deploy/notion-sync.env.example`,
`docs/notion-sync-setup.md`, `README.md`.
Interfaces: `Journal`, `sync_page`, CLI `python -m colf.notion_sync.run [--dry-run]`.

- [x] Test prima del codice e run rosso.
- [x] Persistenza data prima osservazione e preparazione, lock, anteprima senza
  scritture remote o stato persistente, config indipendente dalle fatture.
- [x] Test recupero tick fallito senza riclassificazione/reimportazione, retry
  dopo cambio mese, cancellazioni, journal perso, modifiche e tick rimossi.
- [x] Timer ogni 30 minuti e istruzioni setup/backup/ripristino.
- [x] Revisione indipendente: trovati problemi di integrità, incluso il cambio anno; aggiunti test
  rossi riproducibili e correzioni, tutti verdi nel run successivo.
- [ ] Prova su copie Notion/Google con secondo controllo e nuova spesa.
- [x] Dry-run dati reali; blocco Bea vuoto e compatibile, nessuna migrazione necessaria.
- [x] Configurazione VPS e attivazione timer dopo validazione accessi/layout.

## Decisioni di implementazione

- Branch dedicato già richiesto dall'utente; lavoro nella checkout corrente.
- Cancellazioni permesse sostituiscono il vecchio vincolo di sorgente immutabile.
  Mese automatico sostituisce l'intestazione Mese inizialmente proposta.
- Journal SQLite necessario per fissare date e importi attraverso riavvii e
  distinguere generazioni dopo cancellazioni; backup richiesto insieme al ledger.
- Se registro remoto contiene ID assenti nel journal in qualsiasi anno configurato, fallire chiuso; non tentare
  una ricostruzione potenzialmente duplicante. Tick rimossi dopo conferma locale
  diventano conflitti invece di essere ripristinati automaticamente.
- I test di Notion, conversione e Claude sono raccolti in un file client, evitando
  frammentazione superflua. Nessuna modifica al percorso legacy delle spese.
- Nessun commit automatico di codice applicativo né deploy durante il lavoro.

## Comandi di verifica

```sh
.venv/bin/python -m pytest src/tests -q
PYTHONPATH=src .venv/bin/python -m colf.notion_sync.run --help
```

Nessun LSP disponibile nel catalogo tool: diagnostica sostituita da import e test.
Nessun progetto .NET modificato. Prove esterne Notion/Google ancora da eseguire.

## Esito verifiche locali

- Backend: `.venv/bin/python -m pytest src/tests -q` → 190 passed.
- Bot: `src/colf-telegram-bot/.venv/bin/python -m pytest src/colf-telegram-bot/tests -q` → 71 passed.
- `pytest` dalla root con la sola venv backend non raccoglie due moduli bot
  (`test_expense_card`, `test_notification_ingest`) perché mancano telegram/aiohttp
  in quell'ambiente. La suite bot passa nella propria venv, senza cambiare dipendenze.
- CLI --help e import worker senza llama_cpp verificati.
- Prove reali Notion/Google e runtime systemd eseguite sul VPS, documentate in notion-sync-setup.md.

## Modifiche successive richieste dall'utente

- Valuta letta dalla proprietà Select `Valuta` di una pagina interna a un database
  Notion; spese sempre testo libero. Test per proprietà mancante/vuota/tipo errato
  e conversione THB senza intestazione nel corpo.
- Classificazione con modello esplicito `claude-haiku-5-5`; smoke reale riuscito
  su Cena, 711 e Caffe (Cibo fuori, Cibo, Bar). Categorie trasmesse nell'enum JSON.
- Quote Bea sempre appese in coda all'esistente; nessun riordino o riscrittura
  delle vecchie celle. Test anche per giorno precedente aggiunto dopo uno seguente.

Attivazione VPS completata: sei spese importate e tick verificati; seconda
esecuzione confermata senza duplicati. Timer attivo ogni 30 minuti.

## Arrotondamento a 0,05 EUR, formato valuta e allineamento

La richiesta è stata chiarita dall'utente: passi di 5 centesimi, non 50.
Test per 1,73 → 1,75; 1,46 → 1,45; 1,33 → 1,35 e pareggio 0,025 → 0,05.
Con B si divide il convertito prima di arrotondare; quote uguali.
Formato CURRENCY con simbolo € e allineamento RIGHT tramite repeatCell limitato
alle colonne importo, preservando l'allineamento delle descrizioni e categorie.
Suite backend: 190 passed. Correzione mirata dei sei importi e relativi record
Google/SQLite prima del job manuale, con backup e ID originali mantenuti.

## Ereditarietà del formato contabile del foglio

Nuovo test rosso/verde: il formato NUMBER contabile custom già presente deve
arrivare invariato alle nuove celle, invece del formato CURRENCY generico.
`SheetStore._money_format` legge la precedente cella D e passa il formato a
`_write`; fallback euro solo senza riferimento. Ripristinato il pattern di
D43 nelle dodici celle già importate, verificando importi e ledger invariati.
