import logging

logger = logging.getLogger(__name__)

class Discovery:
    """
    Базовый класс Discovery для поиска новых источников лидов.
    """
    def __init__(self):
        self.is_active = True

    async def find_new_sources(self):
        """
        Метод для поиска новых групп и каналов.
        Пока возвращает пустой список, чтобы проект не падал.
        """
        logger.info("Discovery: поиск новых источников...")
        return []
