"""
Модуль модерации и анти-мата
"""
import re
from typing import List

# Список корней или слов для фильтрации (упрощенный пример)
BAD_WORDS_PATTERNS = [
    r'хуй', r'хуе', r'хуи', r'хуя',
    r'пизд',
    r'ебат', r'ебать', r'ебат', r'еблан', r'ебуч',
    r'бляд', r'бля',
    r'сука', r'суку', r'суке',
    r'гандон', r'гондон',
    r'мудак', r'мудач'
]

def contains_bad_words(text: str) -> bool:
    """Проверяет наличие нецензурной лексики в тексте"""
    if not text:
        return False

    text = text.lower()
    for pattern in BAD_WORDS_PATTERNS:
        if re.search(pattern, text):
            return True
    return False
