"""
hunter_standalone - модуль для дедупликации и AI-анализа лидов

Модуль предоставляет:
- HunterDatabase: база данных для предотвращения дубликатов лидов
- LeadHunter: AI-агент для анализа и скоринга лидов
"""
from .database import HunterDatabase
from .hunter import LeadHunter

__all__ = ["HunterDatabase", "LeadHunter"]
