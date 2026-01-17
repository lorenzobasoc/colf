from datetime import datetime
import locale
import parlant.sdk as p

@p.tool
async def get_current_date(context: p.ToolContext) -> p.ToolResult:
    """Tool to get the current date in Italian locale."""
    try:
        locale.setlocale(locale.LC_TIME, 'it_IT.UTF-8')
    except locale.Error:
        pass
    now = datetime.now()

    return p.ToolResult(data={"day": now.day, "month": now.strftime("%B").capitalize()})