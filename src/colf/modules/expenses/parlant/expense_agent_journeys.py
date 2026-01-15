import parlant.sdk as p
from ....infrastructure.agents.general_tools import get_current_date

async def create_message_categorization_journey(agent: p.Agent) -> p.Journey:
    journey = await agent.create_journey(
        title="Categozzazione del messaggio di spesa",
        description="Analizza e categorizza la spesa in base al messaggio che ottieni."
    )

    t0 = await journey.initial_state.transition_to(tool_state=get_current_date, condition="Se nel messaggio non è presente una data esplicita")

    await t0.target.transition_to(chat_state="""Dal messaggio, devi estrarre:
        1. **Categoria**: Una delle Categorie di spesa (con emoji)
        2. **Nome**: Una breve descrizione della spesa (es. "Pizza margherita", "Biglietto autobus", "Netflix")
        3. **Importo**: L'ammontare speso in formato numerico (es. 15.50, 8.00)
        4. **Giorno**: Il giorno del mese (solo numero da 1 a 31)")
        5. **Mese**: Il mese in formato testuale (es. "Gennaio", "Febbraio")"""
    )

    return journey
