import logging
import os
from typing import List, Dict

logger = logging.getLogger(__name__)

DEFAULT_KEYWORDS = ["перепланировка", "ЖК Москва", "ремонт"]

class Discovery:
    """Автопоиск новых каналов и групп для мониторинга.

    При инициализации подхватывает ключевые слова из переменной окружения SCOUT_KEYWORDS
    (через запятую). Если переменная не задана — используется встроенный список.
    """
    
    def __init__(self):
        env = os.getenv("SCOUT_KEYWORDS", "").strip()
        if env:
            self.keywords = [k.strip() for k in env.split(",") if k.strip()]
        else:
            self.keywords = DEFAULT_KEYWORDS.copy()

    def get_keywords(self) -> List[str]:
        return self.keywords
        
    async def find_new_sources(self, keywords: List[str] = None) -> List[Dict]:
        """Поиск новых источников по ключевым словам.

        Пока реализована заглушка: возвращаем набор демонстрационных Telegram-чатов,
        имитирующих найденные ресурсы. В будущем сюда можно подставить реальную
        логику поиска через Telethon / VK API.
        """
        kws = keywords or self.keywords
        logger.info(f"🔍 Discovery: поиск новых источников по {kws}...")
        # Заглушка: несколько популярных чатов/сообществ по теме ЖК/ремонта (примерные ссылки)
        samples = [
            {"link": "https://t.me/novostroyki_moscow", "title": "Новостройки Москвы", "participants_count": 4500},
            {"link": "https://t.me/zhk_moscow_forum", "title": "ЖК Москва — обсуждения", "participants_count": 3200},
            {"link": "https://t.me/remont_mastertips", "title": "Ремонт и отделка — советы", "participants_count": 2700},
            {"link": "https://t.me/kvartiry_msk", "title": "Квартиры Москвы (купля/продажа)", "participants_count": 6100},
            {"link": "https://t.me/stroitelstvo_msk", "title": "Строительство и планировки", "participants_count": 1800},
        ]
        # Фильтруем по наличию ключевого слова в title (примерная логика)
        found = []
        lower_kws = [k.lower() for k in kws]
        for s in samples:
            t = (s.get("title") or "").lower()
            if any(k in t for k in lower_kws) or any(k in s.get("link", "").lower() for k in lower_kws):
                found.append(s)
        # Если ничего не найдено по фильтру — возвращаем всё, чтобы инициализация прошла
        return found or samples
