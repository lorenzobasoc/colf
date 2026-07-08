# CoLF

CoLF is my personal assistant, controlled via Telegram. It covers **expenses**
(including shared ones) and **electronic invoices** — and the intelligence that
reads my messages runs entirely on a **local LLM**, so nothing I type is ever
sent to an external AI service.

## The local LLM

A small quantised model running on my own hardware handles:

- **Categorisation** — picks the right category for a free-text expense.
- **Date extraction** — turns `"ieri"` or `"il 5 marzo"` into a real date.
- **Participant extraction** — pulls out who to split a shared expense with.

## What it does

- **Expenses** — I send a message like `"Esselunga 42,50"` or `"Benzina 60
  ieri"`; CoLF parses it, shows a confirmation card I can correct, and on confirm
  writes it to the right month tab of my Google Sheet. Adding `"… da dividere con
  Giulio e Bea"` splits the total and records what each person owes.
- **Invoices** — issues FatturaPA v1.2 invoices (forfettario RF19) from Telegram
  or a small web UI: generates the XML and sends it to the SdI via PEC, with
  clients and invoices persisted in SQLite.

---

More features will come over time.
