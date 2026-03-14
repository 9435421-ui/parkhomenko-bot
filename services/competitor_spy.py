import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class CompetitorSpy:
    def __init__(self):
        self.geo_monitoring_enabled = False
        logger.info("CompetitorSpy инициализирован (заглушка)")

    async def scan_geo_chats(self) -> List[Dict]:
        """Сканирование гео-чатов (заглушка)"""
        return []

competitor_spy = CompetitorSpy()
