from datetime import datetime
import locale

def get_current_date():
    locale.setlocale(locale.LC_TIME, 'it_IT.UTF-8')
    now = datetime.now()

    return now.day, now.strftime("%B")