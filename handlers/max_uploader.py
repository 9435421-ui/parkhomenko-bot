"""
MAX.ru Uploader Module — заглушка для будущей интеграции
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MaxUploader:
    """Модуль для публикации на MAX.ru (Mail.ru)"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://partner.api.max.ru"
        logger.info("MAX uploader initialized (disabled)")
    
    async def publish_article(
        self,
        title: str,
        content: str,
        image_url: Optional[str] = None,
        tags: Optional[list] = None
    ) -> Optional[str]:
        """Публикация статьи на MAX"""
        logger.info(f"MAX publish requested: {title}")
        return None
    
    async def get_status(self, article_id: str) -> dict:
        """Проверка статуса модерации"""
        return {"status": "unknown"}
