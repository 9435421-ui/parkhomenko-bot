"""
Утилиты для бота
"""
from .yandex_gpt import yandex_gpt, YandexGPTClient
from .knowledge_base import kb, KnowledgeBase

__all__ = ['yandex_gpt', 'YandexGPTClient', 'kb', 'KnowledgeBase']
