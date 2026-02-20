import logging
import os
import asyncio
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
        logger.info(f"🔍 Discovery: запуск глобального поиска по ключевым словам: {kws}...")

        from services.scout_parser import scout_parser

        found_resources = []
        for kw in kws:
            try:
                # 1. Поиск в Telegram
                tg_results = await scout_parser.search_public_channels(kw)
                for res in tg_results:
                    if not any(f["link"] == res["link"] for f in found_resources):
                        found_resources.append(res)

                # 2. Поиск в VK
                vk_results = await scout_parser.search_public_vk_groups(kw)
                for res in vk_results:
                    if not any(f["link"] == res["link"] for f in found_resources):
                        found_resources.append(res)

                # Небольшая пауза между словами для избежания флуда
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Ошибка Discovery при поиске '{kw}': {e}")

        # Если поиск ничего не вернул (например, проблемы с сессией), используем эталонные чаты как fallback
        if not found_resources:
            logger.info("⚠️ Глобальный поиск не дал результатов, используем эталонный список ЖК.")
            found_resources = [
                {"link": "https://t.me/novostroyki_moscow", "title": "Новостройки Москвы", "participants_count": 4500},
                {"link": "https://t.me/zhk_moscow_forum", "title": "ЖК Москва — обсуждения", "participants_count": 3200},
                {"link": "https://t.me/remont_mastertips", "title": "Ремонт и отделка — советы", "participants_count": 2700},
                {"link": "https://t.me/kvartiry_msk", "title": "Квартиры Москвы (купля/продажа)", "participants_count": 6100},
                {"link": "https://t.me/stroitelstvo_msk", "title": "Строительство и планировки", "participants_count": 1800},
            ]

        return found_resources
