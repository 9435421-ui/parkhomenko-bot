"""
Утилиты для работы с временем (МСК)
"""
from datetime import datetime, timedelta, timezone

def get_msk_now() -> datetime:
    """Возвращает текущее время в МСК (UTC+3)"""
    return datetime.now(timezone.utc) + timedelta(hours=3)

def is_working_hours() -> bool:
    """
    Проверяет, является ли текущее время рабочим (МСК).
    Пн-Пт 09:00–20:00, Сб 10:00–13:00, Вс — вых.
    """
    now = get_msk_now()
    weekday = now.weekday()  # 0-Пн, 5-Сб, 6-Вс
    hour = now.hour

    if weekday < 5:  # Пн-Пт
        return 9 <= hour < 20
    elif weekday == 5:  # Сб
        return 10 <= hour < 13
    else:  # Вс
        return False
