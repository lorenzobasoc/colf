"""Helper puri per il promemoria giornaliero dei crediti (spese condivise).

Nessun I/O: formattano il testo del messaggio Telegram e parsano l'orario di
schedulazione da variabile d'ambiente. La chiamata HTTP e la schedulazione
del job vivono in `TelegramBot` (`telegram_bot.py`).
"""
import datetime


def format_debtors_reminder(month: str, debtors: list[dict]) -> str | None:
    """Formatta il messaggio di promemoria crediti. Ritorna None se nessuno
    deve soldi (evita rumore inutile)."""
    if not debtors:
        return None

    lines = [f"💰 Promemoria crediti ({month})", "Hai dei soldi da farti restituire:", ""]
    for debtor in debtors:
        items = debtor.get("items") or []
        breakdown = ", ".join(
            f"{item['description']} {item['amount']}" for item in items
        )
        line = f"• {debtor['name']}: {debtor['total']}€"
        if breakdown:
            line += f" ({breakdown})"
        lines.append(line)

    return "\n".join(lines)


def parse_reminder_time(raw: str | None, default: str = "09:00") -> datetime.time:
    """Parsa un orario "HH:MM". Ritorna l'orario di default se `raw` è
    mancante o non valido."""
    value = raw if raw else default
    try:
        hour_str, minute_str = value.split(":")
        return datetime.time(int(hour_str), int(minute_str))
    except (ValueError, TypeError):
        default_hour_str, default_minute_str = default.split(":")
        return datetime.time(int(default_hour_str), int(default_minute_str))
