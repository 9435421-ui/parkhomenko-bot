"""
VK Parser — мониторинг групп ВКонтакте.
Проверяет новые посты по ключевым словам.
"""
import asyncio
import logging
import re
from typing import Optional, List, Dict
import aiohttp
from dotenv import load_dotenv

from config import VK_TOKEN, NOTIFICATIONS_CHANNEL_ID, THREAD_ID_LOGS, SPY_KEYWORDS

load_dotenv()

logger = logging.getLogger(__name__)

# VK API version
VK_API_VERSION = "5.199"


class VKParser:
    """Парсер групп ВКонтакте"""
    
    def __init__(self, token: str):
        self.token = token
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _request(self, method: str, params: dict) -> Optional[dict]:
        """Вызов VK API"""
        params["access_token"] = self.token
        params["v"] = VK_API_VERSION
        
        url = f"https://api.vk.com/method/{method}"
        
        try:
            async with self.session.get(url, params=params) as resp:
                data = await resp.json()
                if "error" in data:
                    logger.error(f"VK API error: {data['error']}")
                    return None
                return data.get("response")
        except Exception as e:
            logger.error(f"VK request error: {e}")
            return None
    
    async def connect(self):
        """Подключение сессии"""
        self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Закрытие сессии"""
        if self.session:
            await self.session.close()
    
    async def get_group_id(self, screen_name: str) -> Optional[int]:
        """Получение ID группы по короткому имени"""
        # Убираем vk.com/ если есть
        screen_name = screen_name.replace("vk.com/", "")
        
        result = await self._request("groups.getById", {"group_id": screen_name})
        if result and len(result) > 0:
            return result[0]["id"]
        return None
    
    async def get_posts(self, group_id: int, count: int = 10) -> List[Dict]:
        """Получение последних постов группы"""
        result = await self._request("wall.get", {
            "owner_id": -group_id,
            "count": count,
            "filter": "owner"
        })
        
        if result and "items" in result:
            return result["items"]
        return []
    
    def check_keywords(self, text: str) -> Optional[str]:
        """Проверка текста на ключевые слова"""
        if not text:
            return None
        
        text_lower = text.lower()
        for keyword in SPY_KEYWORDS:
            if keyword.lower() in text_lower:
                return keyword
        return None
    
    async def forward_to_tg(self, post: dict, group_name: str, keyword: str):
        """Пересылка поста в Telegram"""
        from aiogram import Bot
        
        bot = Bot(token=self.session.get("_bot_token") if self.session else None)
        
        try:
            text = post.get("text", "")
            post_id = post.get("id")
            owner_id = post.get("owner_id")
            
            # Формируем ссылку
            group_id = abs(owner_id)
            link = f"https://vk.com/wall-{group_id}_{post_id}"
            
            message = f"""📘 <b>Лид из VK!</b>

💬 <b>Ключевое слово:</b> {keyword}
📍 <b>Группа:</b> {group_name}

📝 <b>Текст:</b>
{text[:500]}

🔗 <a href="{link}">Открыть в VK</a>

👉 <a href="https://t.me/TERION_KvizBot?start=quiz">КВИЗ</a> | <a href="tg://user?id=unknown">Написать</a>"""
            
            # Бот для отправки в TG
            from config import BOT_TOKEN
            tg_bot = Bot(token=BOT_TOKEN)
            
            await tg_bot.send_message(
                chat_id=NOTIFICATIONS_CHANNEL_ID,
                message_thread_id=THREAD_ID_LOGS,
                text=message,
                parse_mode="HTML"
            )
            
            logger.info(f"✅ VK лид переслан: {keyword} из {group_name}")
            
            await tg_bot.session.close()
            
        except Exception as e:
            logger.error(f"❌ Ошибка пересылки VK: {e}")


async def check_vk_groups(groups: List[str]):
    """Проверка групп ВК на новые посты"""
    if not VK_TOKEN:
        logger.error("VK_TOKEN не найден")
        return
    
    parser = VKParser(VK_TOKEN)
    await parser.connect()
    
    try:
        for group_url in groups:
            logger.info(f"🔍 Проверяю группу: {group_url}")
            
            # Получаем ID группы
            group_id = await parser.get_group_id(group_url)
            if not group_id:
                logger.error(f"Не удалось получить ID группы: {group_url}")
                continue
            
            # Получаем посты
            posts = await parser.get_posts(group_id, count=5)
            
            for post in posts:
                text = post.get("text", "")
                keyword = parser.check_keywords(text)
                
                if keyword:
                    # Найден ключевик!
                    group_name = group_url.replace("vk.com/", "")
                    logger.info(f"🔔 Найден VK лид: {keyword} в {group_name}")
                    
                    # Здесь можно добавить логику пересылки
                    # await parser.forward_to_tg(post, group_name, keyword)
                    
    finally:
        await parser.close()


async def start_vk_monitoring(groups: List[str], interval: int = 300):
    """
    Запуск мониторинга VK групп.
    
    Args:
        groups: Список групп для мониторинга (['himki', 'moscow', ...])
        interval: Интервал проверки в секундах (по умолчанию 5 минут)
    """
    logger.info("🚀 Запуск мониторинга VK групп...")
    
    while True:
        try:
            await check_vk_groups(groups)
        except Exception as e:
            logger.error(f"Ошибка мониторинга VK: {e}")
        
        await asyncio.sleep(interval)


if __name__ == "__main__":
    # Пример использования
    test_groups = ["himki", "moscow"]  # Замените на свои группы
    
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_vk_monitoring(test_groups))
