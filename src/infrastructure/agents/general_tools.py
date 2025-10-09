from datetime import datetime

def get_current_date():
    now = datetime.now()

    return now.day, now.strftime("%B")