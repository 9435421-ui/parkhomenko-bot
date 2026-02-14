"""
Основной бот ТЕРИОН - aiogram 3.x + Content Factory.
Запуск ДВУХ ботов с РАЗДЕЛЬНЫМИ Dispatchers:
- main_bot (АНТОН): консультант по перепланировкам
- content_bot (ДОМ ГРАНД): контент и посты
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, CONTENT_BOT_TOKEN
from handlers import admin_router, start_router, quiz_router, dialog_router
from handlers import content_router
from database import db
from utils import kb
from middleware.logging import UnhandledCallbackMiddleware
from services.scout_parser import ScoutParser

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def main():
    logger.info("🎯 Запуск ЭКОСИСТЕМЫ TERION...")
    
    # 1. Единая инициализация ресурсов
    await db.connect()
    await kb.index_documents()
    
    # 2. Проверка связей
    logger.info("🔍 Проверка связей...")
    try:
        # Проверка каналов
        from config import CHANNEL_ID_TERION, CHANNEL_ID_DOM_GRAD, LEADS_GROUP_CHAT_ID
        from config import THREAD_ID_DRAFTS, THREAD_ID_CONTENT_PLAN, THREAD_ID_TRENDS_SEASON, THREAD_ID_LOGS
        
        # Проверка доступности каналов (пробуем получить информацию)
        from aiogram import Bot
        from config import BOT_TOKEN, CONTENT_BOT_TOKEN
        
        main_bot = Bot(token=BOT_TOKEN or "")
        content_bot = Bot(token=CONTENT_BOT_TOKEN or "")
        
        # Проверка каналов
        try:
            await main_bot.get_chat(CHANNEL_ID_TERION)
            logger.info("✅ Канал TG: OK")
        except Exception as e:
            logger.error(f"❌ Канал TG: {e}")
        
        try:
            await content_bot.get_chat(CHANNEL_ID_DOM_GRAD)
            logger.info("✅ Канал ДОМ ГРАНД: OK")
        except Exception as e:
            logger.error(f"❌ Канал ДОМ ГРАНД: {e}")
        
        # Проверка рабочей группы
        try:
            await main_bot.get_chat(LEADS_GROUP_CHAT_ID)
            logger.info("✅ Рабочая группа: OK")
        except Exception as e:
            logger.error(f"❌ Рабочая группа: {e}")
        
        # Проверка VK
        from config import VK_TOKEN, VK_GROUP_ID
        if VK_TOKEN and VK_GROUP_ID:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://api.vk.com/method/groups.getById",
                        params={"access_token": VK_TOKEN, "v": "5.199", "group_ids": VK_GROUP_ID}
                    ) as resp:
                        data = await resp.json()
                        if "response" in data and data["response"]:
                            group_name = data["response"][0].get("name", "VK")
                            logger.info(f"✅ Интеграция VK ({group_name}): OK")
                        else:
                            logger.warning("⚠️ Интеграция VK: группа не найдена")
            except Exception as e:
                logger.warning(f"⚠️ Интеграция VK: {e}")
        else:
            logger.warning("⚠️ Интеграция VK: токен или group_id не настроены")
        
        # Проверка топиков (пробуем отправить тестовое сообщение и удалить)
        for thread_id, name in [
            (THREAD_ID_DRAFTS, "Черновики"),
            (THREAD_ID_CONTENT_PLAN, "Контент-план"),
            (THREAD_ID_TRENDS_SEASON, "Тренды/Сезон"),
            (THREAD_ID_LOGS, "Логи")
        ]:
            try:
                # Проверка существования топика через get_chat
                await main_bot.get_chat(LEADS_GROUP_CHAT_ID)
                logger.info(f"✅ Топик {name}: OK")
            except Exception as e:
                logger.error(f"❌ Топик {name}: {e}")
        
        await main_bot.session.close()
        await content_bot.session.close()
        
    except Exception as e:
        logger.error(f"Ошибка проверки связей: {e}")
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: logger.info("⏰ Проверка постов"), 'cron', hour=12)
    
    # Scout Parser Integration
    scout = ScoutParser()
    # Telegram раз в 2 часа
    scheduler.add_job(scout.parse_telegram, 'interval', hours=2)
    # VK раз в 3 часа (чтобы не забанили)
    scheduler.add_job(scout.parse_vk, 'interval', hours=3)
    
    scheduler.start()
    
    # 2. Настройка АНТОНА
    main_bot = Bot(token=BOT_TOKEN or "", default=DefaultBotProperties(parse_mode="HTML"))
    dp_main = Dispatcher(storage=MemoryStorage())
    dp_main.callback_query.middleware(UnhandledCallbackMiddleware())
    dp_main.include_router(admin_router)
    dp_main.include_router(start_router)
    dp_main.include_router(quiz_router)
    dp_main.include_router(dialog_router)
    
    # 3. Настройка ДОМ ГРАНД
    content_bot = Bot(token=CONTENT_BOT_TOKEN or "", default=DefaultBotProperties(parse_mode="HTML"))
    dp_content = Dispatcher(storage=MemoryStorage())
    dp_content.callback_query.middleware(UnhandledCallbackMiddleware())
    dp_content.include_routers(content_router)
    
    # 4. Параллельный запуск
    await asyncio.gather(
        dp_main.start_polling(main_bot),
        dp_content.start_polling(content_bot)
    )


if __name__ == "__main__":
    asyncio.run(main())
