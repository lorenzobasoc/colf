# Importazione spese Notion → Colf → Google Sheets

Branch: `feat/notion-expense-sync`. Specifica aggiornata dopo le indicazioni
utente: controllo ogni 30 minuti, nessun mese esplicito, cancellazioni manuali
consentite dopo importazione, valuta nella pagina e tick per ogni spesa.

## Comportamento

```text
9
Cena 130 B
711 130 B

10
Caffe 110 B
Tempio 100
```

Un giorno apre il gruppo, ogni riga seguente è descrizione/importo e B facoltativa.
`711 130 B` conserva `711` come descrizione. Indentazione e righe vuote tollerate.
Proprietà Select `Valuta` con codice ISO obbligatoria per pagina; supportate più pagine configurate.
Cambiare valuta riguarda spese nuove; quelle già preparate conservano il tasso.

Mese/anno del primo rilevamento, nel fuso `SYNC_TIMEZONE` (impostare Asia/Bangkok
se desiderato), fissati nel journal locale per i retry. Giorno futuro o non
valido nel mese: errore; nessuna deduzione silenziosa del mese precedente.
Le spese del mese passato vanno svuotate prima del cambio mese.

A:D segue `local-llm`: giorno, descrizione, categoria Colf con etichetta esistente,
quota personale. B = 50% con Bea; solo la sua quota va in G:H da G23, riga giorno
in G, poi descrizione/importo, una riga vuota tra giorni. Nuove quote sempre in coda; si scrivono solo le nuove celle. Valori numerici EUR con
formato due decimali. Non si scrive in I; layout vecchio G25:I44 da migrare
manualmente prima dell'attivazione. Vecchi writer e reminder debitori sullo
stesso foglio devono essere disattivati.

Cambio storico ECB via Frankfurter, ultimo disponibile entro sette giorni,
mai futuro; EUR = 1. Decimal e ROUND_HALF_UP al multiplo di 0,05 EUR più
vicino. Con B dividere prima il convertito esatto e arrotondare la metà: quota
personale e Bea uguali. Nessun arrotondamento intermedio al centesimo. Esempio:
130 × 0,026677 / 2 = 1,734005 → 1,75 EUR ciascuno. Il totale contabilizzato è
approssimato e può differire dal convertito esatto. Formato celle valuta euro
con simbolo finale, due decimali e allineamento a destra; è un cambio di riferimento, non della carta.

## Architettura e alternative

Timer systemd ogni 30 minuti, comando Python one-shot, lock esclusivo. Alternativa
considerata: Routines cloud Claude; qui il VPS permette di controllare Notion
senza interrogare Claude quando non ci sono spese nuove. Nessun browser.
Claude Code originale con login abbonamento, modello fissato a Haiku 5.5
(`claude-haiku-5-5`), senza API di inferenza: riceve
solo ID/descrizioni/categorie, restituisce JSON validato, senza strumenti.
Date, calcoli, split e scritture sono deterministici. Worker indipendente da
llama.cpp e dalle credenziali fatture.

## Stato e affidabilità

Journal SQLite persistente con identità, data prima osservazione e preparazione
immutabile; tab nascosto Google `_colf_imports` con i record contabili completi.
Una sola batchUpdate atomica aggiorna A:D, G:H, formati e registro. Poi si
rileggono i blocchi Notion e si aggiunge ` ✅` alla singola riga preservando
rich text e righe estranee. Righe già marcate al primo avvio sono ignorate.

Risposta Google persa: prossimo controllo rilegge il registro, senza retry cieco.
Tick fallito: prossimo controllo riprova solo Notion. Journal locale mancante o
incoerente con registro: arresto, ripristinare backup. Dati originali, categoria,
valuta, cambio/data e quote restano registrati. È necessario conservare entrambi
journal e registro, non eliminare uno dei due per ripartire.

Cancellare righe importate è consentito: non cancella dati nel foglio e non genera
errori. Se rimangono righe da importare, conservarne il giorno. L'identità delle
righe usa pagina/blocco/contenuto/occorrenza, non posizione assoluta, e una nuova
generazione viene assegnata dopo una cancellazione osservata dal worker.

Nuovi acquisti vanno aggiunti in nuovi paragrafi Notion. Gli a capo nello stesso
paragrafo sono supportati, ma sostituire righe già registrate nello stesso blocco
è ambiguo: il worker si ferma. Rimuovere un tick già confermato localmente è un
conflitto, non un ordine di reimportazione. Non sono previste correzioni contabili
automatiche dopo modifiche alla pagina. Il testo non permette di distinguere
ogni cancellazione/ricreazione identica avvenuta tra due controlli: usare blocchi
nuovi per acquisti nuovi. Due acquisti identici in blocchi distinti restano distinti.

Notion non offre una transazione con Google né compare-and-swap: resta una gara
residua fra rilettura e PATCH. Evitare modifiche durante l'importazione.

## Verifica e rilascio

Test automatici con servizi simulati, CLI --help e smoke reale di classificazione
Claude. Prima di attivare timer: pagina Notion e Google Sheet di test, dry-run,
importazione, tick, secondo run senza duplicati; poi anteprima sui dati reali.
Non sono state eseguite scritture su Notion/Google nel workspace.

Fuori scope: split generici, rimborsi, migrazione automatica vecchi debiti,
correzioni retroattive, nuova UI ed esportazione Excel. Setup e recupero in
`docs/notion-sync-setup.md`.

Fonti verificate: https://developers.notion.com/reference/get-block-children,
https://developers.notion.com/reference/update-a-block,
https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/batchUpdate,
https://code.claude.com/docs/en/headless, https://frankfurter.dev/.
