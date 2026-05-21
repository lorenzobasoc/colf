from datetime import date
from google.oauth2.service_account import Credentials
import json
import gspread

def _format_input(expense_classification_json):
    if isinstance(expense_classification_json, str):
        spese_input = json.loads(expense_classification_json)
    else:
        spese_input = expense_classification_json
        
    if isinstance(spese_input, dict):
        spese_input = [spese_input]
        
    return spese_input

def inserisci_spese_agente(expense_classification_json, credentials_path="../../../../.keys/sheets_mcp_service_account.json"):
    if not expense_classification_json:
        print("Errore: Nessuna spesa fornita in input.")
        return
    
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
    gc = gspread.authorize(creds)
    
    spese_input = _format_input(expense_classification_json)
    
    nome_spreadsheet_target = f"Spese {date.today().year}"
    
    all_spreadsheets = gc.openall()
    
    spreadsheet_selezionato = None
    for sh in all_spreadsheets:
        if sh.title == nome_spreadsheet_target:
            spreadsheet_selezionato = sh
            break
            
    if not spreadsheet_selezionato:
        raise FileNotFoundError(f"ERRORE critico: Non è stato trovato lo spreadsheet con titolo '{nome_spreadsheet_target}'.")
        
    worksheets = spreadsheet_selezionato.worksheets()
    nomi_fogli = [ws.title for ws in worksheets]
    
    spese_per_mese = {}
    for spesa in spese_input:
        mese = spesa.get("mese")
        if not mese:
            continue
        if mese not in spese_per_mese:
            spese_per_mese[mese] = []
        spese_per_mese[mese].append(spesa)
        
    for mese_target, lotto_spese in spese_per_mese.items():
        if mese_target not in nomi_fogli:
            raise ValueError(f"ERRORE critico: Il foglio relativo al mese '{mese_target}' non esiste nello spreadsheet.")
        
        foglio_mese = spreadsheet_selezionato.worksheet(mese_target)
        
        tutti_i_dati = foglio_mese.get("A1:D")
        numero_righe_totali = len(tutti_i_dati)
        
        if numero_righe_totali == 0:
            intestazioni = ["Data", "Descrizione", "Tipologia", "Importo"]
            foglio_mese.update("A1:D1", [intestazioni])
            tutti_i_dati = [intestazioni]
            numero_righe_totali = 1
            
        prima_riga_vuota = numero_righe_totali + 1
        
        array_2d_spese = []
        dettaglio_report = []
        for spesa in lotto_spese:
            data = spesa.get("data")
            descrizione = spesa.get("nome")
            tipologia = spesa.get("categoria")
            importo = spesa.get("importo")
            
            riga = [data, descrizione, tipologia, importo]
            array_2d_spese.append(riga)
            
            dettaglio_report.append({
                "Data": data,
                "Descrizione": descrizione,
                "Tipologia": tipologia,
                "Importo": importo
            })

        numero_spese_da_inserire = len(array_2d_spese)
        riga_inizio = prima_riga_vuota
        riga_fine = prima_riga_vuota + numero_spese_da_inserire - 1
        range_inserimento = f"A{riga_inizio}:D{riga_fine}"
    
        foglio_mese.update(range_inserimento, array_2d_spese)

# if __name__ == "__main__":
#     json_input_esempio = [
#         {
#             "categoria": "🍔 Cibo fuori",
#             "nome": "Pizza margherita",
#             "importo": "12,00",
#             "data": "21",
#             "mese": "Maggio"
#         },
#         {
#             "categoria": "🚗 Auto",
#             "nome": "Benzina",
#             "importo": "45,50",
#             "data": "15",
#             "mese": "Aprile"
#         }
#     ]
    
#     try:
#         inserisci_spese_agente(json_input_esempio)
#     except Exception as e:
#         print(f"\n[Nota per l'esecuzione]: {e}")