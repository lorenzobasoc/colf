import parlant.sdk as p
from ...infrastructure.agents.general_tools import get_current_date

async def add_expense_to_google_sheets(agent: p.Agent) -> p.Journey:
    journey = await agent.create_journey(
        title="Inserimento Spese su Google Sheets (MCP)",
        description="Gestisce il processo di inserimento spese interagendo con il server MCP di Google Sheets.",
        conditions=["L'utente ha confermato l'inserimento della spesa"]
    )

    t0 = await journey.initial_state.transition_to(
        chat_state="""
        ## STEP 1: Identifica lo spreadsheet
        Devi trovare lo spreadsheet corretto per le spese dell'anno corrente (es. "Spese 2025").
        
        Esegui l'operazione per listare i file disponibili.
        [Use the mcp-google-sheets:list_spreadsheets]

        ## STEP 2: Identifica il foglio del mese
        Analizza la lista degli spreadsheet ricevuta. Identifica lo `spreadsheet_id` del file "Spese {ANNO_CORRENTE}".
        
        Ora devi trovare il foglio (tab) corrispondente al mese della spesa (es. "Gennaio", "Ottobre").
        Richiedi la lista dei fogli per questo spreadsheet.
        [Use the mcp-google-sheets:list_sheets]

        ## STEP 3: Recupera dati per calcolo riga
        Hai identificato il nome del foglio del mese corrente. Ora dobbiamo calcolare dove scrivere.
        
        Recupera i dati dal range "A1:D" impostando `include_grid_data` su False.
        Questo serve per contare le righe esistenti e trovare la prima riga vuota.
        
        [Use the mcp-google-sheets:get_sheet_data]

        ## STEP 4: Calcolo e Inserimento
        Analizza i dati appena ricevuti:
        1. Conta le righe totali (inclusa intestazione).
        2. **CALCOLA LA PRIMA RIGA VUOTA**: `righe_totali + 1`.
           - Se hai 10 righe occupate -> Scrivi alla 11.
           - Se hai solo l'header (1 riga) -> Scrivi alla 2.
        
        Prepara i dati nel formato array 2D: `[[Data, Nome, Categoria, Importo]]`.
        Ignora il campo "mese" per i dati, usalo solo per selezionare il foglio.
        
        Costruisci il range di destinazione (es. "A11:D11") e inserisci la spesa.
        [Use the mcp-google-sheets:update_cells]
        """
    )

    await t0.target.transition_to(
        state=p.END_JOURNEY,
        condition="L'operazione di update_cells è stata completata con successo",
        chat_state="""
        ## STEP 5: Report Finale
        L'inserimento è stato completato. Fornisci un riepilogo all'utente includendo:
        1. Spreadsheet e Foglio utilizzati.
        2. La riga in cui hai scritto la spesa.
        3. I dettagli della spesa inserita.
        
        Conferma che l'operazione è conclusa.
        """
    )

    return journey

async def create_message_categorization_journey(agent: p.Agent) -> p.Journey:
    journey = await agent.create_journey(
        title="Categozzazione del messaggio di spesa",
        description="Analizza e categorizza la spesa in base al messaggio che ottieni.",
        conditions=["Il messaggio contiene una spesa da classificare o inserire"]
    )

    t0 = await journey.initial_state.transition_to(tool_state=get_current_date, condition="Se nel messaggio non è presente una data esplicita")

    t1 = await t0.target.transition_to(chat_state="""Dal messaggio, devi estrarre:
        1. **Categoria**: Una delle Categorie di spesa (con emoji)
        2. **Nome**: Una breve descrizione della spesa (es. "Pizza margherita", "Biglietto autobus", "Netflix")
        3. **Importo**: L'ammontare speso in formato numerico (es. 15.50, 8.00)
        4. **Giorno**: Il giorno del mese (solo numero da 1 a 31)")
        5. **Mese**: Il mese in formato testuale (es. "Gennaio", "Febbraio")
        
        Una volta estratti questi elementi, devi ritornarli all'utente in formato JSON come specificato nelle guidelines.
        """
    )

    t2 = await t1.target.transition_to(chat_state="Chiedi all'utente se le informazioni sono corrette e puoi procedere con il caricamento sul foglio di spesa")

    await t2.target.transition_to(journey=add_expense_to_google_sheets, condition="L'utente ha confermato l'inserimento della spesa")

    await t2.target.transition_to(state=p.END_JOURNEY, condition="L'utente non ha confermato l'inserimento della spesa")

    return journey
