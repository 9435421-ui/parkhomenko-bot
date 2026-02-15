"""Ссылка на планировщик APScheduler для отображения очереди задач в меню."""
from typing import Optional

_scheduler = None


def set_scheduler(scheduler):
    global _scheduler
    _scheduler = scheduler


def get_scheduler():
    return _scheduler
