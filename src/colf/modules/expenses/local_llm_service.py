import os
import json
import logging
from datetime import datetime
from pathlib import Path
from llama_cpp import Llama
from ...modules.expenses.agents.agents_utils import read_prompt_file

from ..agents.agents_utils import read_prompt_file, clean_agent_response

logger = logging.getLogger(__name__)

class LocalLLMService:
    def __init__(self):
        self.model_path = os.getenv('MODEL_PATH')
        if not self.model_path:
            logger.error("MODEL_PATH not set in environment variables.")
            raise ValueError("MODEL_PATH environment variable is required.")
        
        try:
            self.llm = Llama(
                model_path=self.model_path,
                n_ctx=4096, # Adjust context window if needed
                verbose=False
            )
        except Exception as e:
            logger.error(f"Failed to load Llama model at {self.model_path}: {e}")
            raise

        # Load the prompt
        # Assuming the prompt is at src/colf/modules/expenses/agents/prompts/expense_message_categorizer_agent_prompt.md
        # We need to reach it from valid path.
        # Let's find absolute path or relative from here.
        # file: src/colf/infrastructure/llm/local_llm_service.py
        # prompt: src/colf/modules/expenses/agents/prompts/...
        
        base_path = Path(__file__).resolve().parent.parent.parent # src/colf
        self.prompt_path = base_path / "modules" / "expenses" / "agents" / "prompts" / "expense_message_categorizer_agent_prompt.md"
        
        if not self.prompt_path.exists():
             # Fallback or error. Try to find it via the module structure if possible.
             # Or just hardcode the path structure relative to project root.
             logger.warning(f"Prompt file not found at {self.prompt_path}")

        self.system_prompt_template = read_prompt_file(self.prompt_path) if self.prompt_path.exists() else ""

    def categorize_expense(self, text: str) -> dict:
        """
        Categorizes the expense text using the local LLM.
        Returns a dictionary representing the categorized expense.
        """
        # Inject current date into the prompt context since we are not using tools
        current_date_str = datetime.now().strftime("%d %B %Y")
        
        # Modify the system prompt to include the date instruction directly
        # and remove the requirement to use the tool if date is missing (implying 'today').
        # However, modifying the prompt text dynamically is safer.
        
        
        system_instruction = f"""
{self.system_prompt_template}

DATI DI CONTESTO ATTUALI:
Oggi è il {current_date_str}.
Se la data non è specificata nel messaggio, usa la data di oggi.
NON chiamare nessun tool.
"""

        # Structuring the prompt for Llama
        # Simple chat format
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": text}
        ]
        
        try:
            response = self.llm.create_chat_completion(
                messages=messages,
                temperature=0.1,
                max_tokens=1024
            )
            
            content = response['choices'][0]['message']['content']
            logger.info(f"LLM Response: {content}")
            
            cleaned_content = clean_agent_response(content)
            
            # Extract JSON
            # Sometimes models wrap in markdown ```json ... ```
            # clean_agent_response handles that.
            
            data = json.loads(cleaned_content)
            return data
            
        except Exception as e:
            logger.error(f"Error categorizing expense: {e}")
            raise

