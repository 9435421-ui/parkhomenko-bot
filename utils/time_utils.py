import datetime

def get_moscow_now():
    """Возвращает текущее время в Москве (UTC+3)"""
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))


def is_working_hours():
    """Проверяет, является ли текущее время рабочим (Пн-Пт, 09:00-19:00 МСК)"""
    now = get_moscow_now()
    # Пн-Пт (0-4)
    if now.weekday() > 4:
        return False
    # 09:00 - 19:00
    if 9 <= now.hour < 19:
        return True
    return False
