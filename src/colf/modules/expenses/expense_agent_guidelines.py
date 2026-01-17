import parlant.sdk as p

async def add_guidelines(agent: p.Agent) -> None:
    await agent.create_guideline(
        condition="La categoria non è esplicitamente presente nel messaggio",
        action="Deducila dal contesto, scegliedola tra le Categorie di spesa"
    )

    await agent.create_guideline(
        condition="Il prezzo non è in formato italiano (es. 15,50)",
        action="Convertirlo in formato italiano (es. 1.050,34)"
    )

    await agent.create_guideline(
        condition="La data è espressa in forma testuale (es. 'oggi', 'ieri')",
        action="Usa il tool per ottenere la data corrente e dedurla"
    )

    await agent.create_guideline(
        condition="Hai estratto tutte le informazioni",
        action="Restituiscile in formato JSON con le chiavi: categoria, nome, importo, giorno, mese SENZA aggiungere ulteriore testo"
    )