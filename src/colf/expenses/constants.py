CATEGORIES: dict[str, str] = {
    "Cibo": "🍲 Cibo/Spesa",
    "Cibo fuori": "🍔 Cibo fuori",
    "Bar": "🍺 Bar",
    "Trasporti": "🚌 Trasporti",
    "Auto": "🚗 Auto",
    "Casa": "🏠 Casa",
    "Sanita": "🚑 Sanità",
    "Vestiti": "👕 Vestiti",
    "Abbonamenti": "🎫 Abbonamenti",
    "Viaggi": "✈️ Viaggi",
    "Eventi": "🕺 Festa/Eventi",
    "Sport": "⛰️ Sport",
    "Regali": "🎁 Regali",
    "Lavoro": "💻 Lavoro",
    "Intrattenimento": "🍿 Intrattenimento",
    "Altro": "🌟 Altro extra",
}

FALLBACK_CATEGORY = "Altro"

ITALIAN_MONTHS: tuple[str, ...] = (
    "Gennaio",
    "Febbraio",
    "Marzo",
    "Aprile",
    "Maggio",
    "Giugno",
    "Luglio",
    "Agosto",
    "Settembre",
    "Ottobre",
    "Novembre",
    "Dicembre",
)

SHEET_HEADERS: list[str] = ["Data", "Descrizione", "Tipologia", "Importo"]

SPREADSHEET_NAME_TEMPLATE = "Spese {year}"
