import os

from dotenv import load_dotenv
from llama_cpp import Llama

load_dotenv()

SYSTEM_PROMPT = """You are a local text classification assistant. Your sole task is to analyze the user's expense and respond EXCLUSIVELY with the name of one category from the list below.

    CRITICAL RULES:
    1. Respond with ONLY the category name (one or two words maximum).
    2. DO NOT include emojis.
    3. DO NOT add punctuation, introductions, explanations, or extra spaces.
    4. Always output the exact Italian category name as written in the list below.

    ALLOWED CATEGORIES:
    - Cibo
    - Cibo fuori
    - Bar
    - Trasporti
    - Auto
    - Casa
    - Sanita
    - Vestiti
    - Abbonamenti
    - Viaggi
    - Eventi
    - Sport
    - Regali
    - Lavoro
    - Intrattenimento
    - Altro

    CLASSIFICATION GUIDE:
    - Supermarket, groceries, Aldi, Unes, ingredients -> Cibo
    - Restaurant, pizza, McDonald, KFC, sushi, kebab, sandwich, dinner -> Cibo fuori
    - Coffee, cafe, spritz, beer, breakfast, aperitivo, cornetto -> Bar
    - Train, metro, bus, ticket, toll, pedaggio -> Trasporti
    - Gas, gasoline, benzina, benza, car insurance -> Auto
    - Netflix, Spotify, Amazon Prime, subscription -> Abbonamenti
    - Cinema, concert, theatre -> Intrattenimento
    - If uncertain -> Altro"""

def categorize_expense(message: str) -> str:
    llm = Llama(
        model_path=f"../../models/{os.getenv('LLM_NAME')}",
        n_ctx=1024,
        chat_format="chatml",
        verbose=False
    )

    response = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message}
        ],
        temperature=0.0,   # Rimuove la creatività (decodifica greedy)
        max_tokens=10      # Genera solo i token della categoria
    )
    
    return response["choices"][0]["message"]["content"].strip()

if __name__ == "__main__":
    # Test pratico
    spesa = "Birra al bar 12 euro"
    risultato = categorize_expense(spesa)
    
    print(f"\n[Test] Spesa: '{spesa}'")
    print(f"[Risultato] Categoria: {risultato}")
