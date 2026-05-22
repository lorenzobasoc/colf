import logging
import re
from datetime import date, timedelta

from llama_cpp import Llama

from ..text_parsing import strip_amount

logger = logging.getLogger(__name__)

_DATE_PATTERN = re.compile(r"\b(\d{1,2})/(\d{1,2})\b")


def _build_system_prompt(today: date, yesterday: date, day_before: date) -> str:
    m = today.strftime("%m")
    return f"""You are a date extraction assistant. Extract the date from an Italian expense message.

Output ONLY a date in DD/MM format. Nothing else.

IMPORTANT: Numbers like 23, 56, 42, 15, 12, 60 are PRICES — ignore them completely.
Only these patterns are dates: "ieri", "oggi", "l'altro ieri", "il N", "DD/MM", "N nomemese".
"il N" means day N of the CURRENT month ({m}).

Today={today.strftime('%d/%m')}, yesterday={yesterday.strftime('%d/%m')}, day_before_yesterday={day_before.strftime('%d/%m')}, current_month={m}.

Examples:
"Birra al bar 23 ieri" → {yesterday.strftime('%d/%m')}
"Caffè 5 ieri" → {yesterday.strftime('%d/%m')}
"Cena sushi 56 il 31/12" → 31/12
"Spesa esselunga 42,50" → {today.strftime('%d/%m')}
"Cinema 15 il 3" → 03/{m}
"Pranzo 12 5 marzo" → 05/03
"Benzina 60 l'altro ieri" → {day_before.strftime('%d/%m')}
"Palestra 30 oggi" → {today.strftime('%d/%m')}"""


def extract_date(message: str, llm: Llama) -> date:
    today = date.today()
    yesterday = today - timedelta(days=1)
    day_before = today - timedelta(days=2)

    response = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": _build_system_prompt(today, yesterday, day_before)},
            {"role": "user", "content": f"Expense: {strip_amount(message)}"},
        ],
        temperature=0.0,
        max_tokens=8,
    )
    raw = response["choices"][0]["message"]["content"].strip()

    m = _DATE_PATTERN.search(raw)
    if m:
        try:
            return date(today.year, int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    logger.warning("LLM returned unparseable date %r for %r, falling back to today", raw, message)
    return today
