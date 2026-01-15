from datetime import datetime
import locale
import parlant.sdk as p

@p.tool
def get_current_date(context: p.ToolContext) -> p.ToolResult:
    """Tool to get the current date in Italian locale."""
    locale.setlocale(locale.LC_TIME, 'it_IT.UTF-8')
    now = datetime.now()

    return now.day, now.strftime("%B").capitalize()