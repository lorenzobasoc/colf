# CoLF

CoLF is my personal assistant, controlled via Telegram. For now it covers one thing: **expenses**.

I keep a Google Sheet where I track all my spending. CoLF automates the manual part: I send a message in natural language (e.g. `"Esselunga 42,50"` or `"Benzina 60 ieri"`), and the assistant figures out the amount, description, date, and category — then asks me to confirm before saving anything.

Once confirmed, the expense lands in the right month tab of my spreadsheet automatically. The parsing and categorisation run on a local LLM — no data is sent to external services.

---

More features will come over time. Expenses are just the beginning.
