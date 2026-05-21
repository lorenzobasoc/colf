from datetime import date
import re
from colf.modules.expenses.google_sheets_service import add_expense
from colf.modules.expenses.local_llm_service import categorize_expense

def build_expense_category(categoria: str) -> str:
    mappa_categorie = {
        "cibo/spesa": "🍲 Cibo/Spesa",
        "trasporti": "🚌 Trasporti",
        "casa": "🏠 Casa",
        "sanità": "🚑 Sanità",
        "sanita": "🚑 Sanità",
        "vestiti": "👕 Vestiti",
        "abbonamenti": "🎫 Abbonamenti",
        "bar": "🍺 Bar",
        "cibo fuori": "🍔 Cibo fuori",
        "viaggi": "✈️ Viaggi",
        "festa/eventi": "🕺 Festa/Eventi",
        "sport": "⛰️ Sport",
        "regali": "🎁 Regali",
        "altro extra": "🌟 Altro extra",
        "lavoro": "💻 Lavoro",
        "auto": "🚗 Auto",
        "intrattenimento": "🍿 Intrattenimento",
    }

    chiave = categoria.lower().strip()

    return mappa_categorie.get(chiave, categoria)

def extract_price(testo: str) -> str:
    normalized_text = testo.replace(",", ".")
    match = re.search(r"\d+(\.\d+)?", normalized_text)

    if match:
        valore_str = match.group()
        return valore_str

    return None

def extract_description(testo: str) -> str:
    # 1. Regex che identifica il numero (interi o decimali con punto/virgola)
    # e opzionalmente i simboli di valuta comuni (€, $, £) o la parola 'euro'
    pattern_rimozione = r"\d+([.,]\d+)?\s*(€|\$|£|euro|Euro)?"

    # 2. Sostituisce il pattern trovato con una stringa vuota
    testo_pulito = re.sub(pattern_rimozione, "", testo)

    # 3. Pulisce gli spazi bianchi extra rimasti (es. doppi spazi o spazi finali)
    testo_pulito = re.sub(r"\s+", " ", testo_pulito).strip()

    return testo_pulito

def message_expense_workflow(self, message: str) -> str:        
    categorized_data = categorize_expense(message)
    category = build_expense_category(categorized_data)
    price = extract_price(message)
    description = extract_description(message)

    expense = {
        "data": date.today().day,
        "descrizione": description,
        "tipologia": category,
        "importo": price
    }

    add_expense(expense)            