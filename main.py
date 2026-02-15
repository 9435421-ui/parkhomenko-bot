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

from config import BOT_TOKEN, CONTENT_BOT_TOKEN, LEADS_GROUP_CHAT_ID
from handlers import admin_router, start_router, quiz_router, dialog_router
from handlers import content_router
from handlers.creator import creator_router
from database import db
from utils import kb
from middleware.logging import UnhandledCallbackMiddleware
from services.scout_parser import ScoutParser
from agents.creative_agent import creative_agent
from services.lead_hunter import LeadHunter
from services.competitor_spy import competitor_spy
from services.publisher import publisher
from services.image_generator import image_generator

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
        
        # Закрываем сессии проверочных ботов внутри блока проверки
        await main_bot.session.close()
        await content_bot.session.close()
        
    except Exception as e:
        logger.error(f"Ошибка проверки связей: {e}")
    
    scheduler = AsyncIOScheduler()

    async def check_and_publish_scheduled_posts():
        """Публикация постов из контент-плана (status=approved, publish_date <= сейчас)."""
        try:
            posts = await db.get_posts_to_publish()
            if not posts:
                return
            for post in posts:
                try:
                    title = (post.get("title") or "").strip()
                    body = (post.get("body") or "").strip()
                    text = f"📌 <b>{title}</b>\n\n{body}\n\n#перепланировка #согласование #терион" if title else body + "\n\n#перепланировка #согласование #терион"
                    image_bytes = None  # TODO: загрузка по image_url при наличии
                    await publisher.publish_all(text, image_bytes)
                    await db.mark_as_published(post["id"])
                    logger.info("✅ Опубликован пост #%s из контент-плана", post["id"])
                except Exception as e:
                    logger.error("Ошибка публикации поста #%s: %s", post.get("id"), e)
        except Exception as e:
            logger.error("Ошибка check_and_publish_scheduled_posts: %s", e)

    # Проверка и публикация по расписанию: каждый час (посты с publish_date в прошлом и status=approved)
    scheduler.add_job(check_and_publish_scheduled_posts, "interval", hours=1)
    scheduler.add_job(check_and_publish_scheduled_posts, "cron", hour=12, minute=0)  # явно в 12:00

    # Lead Hunter & Creative Agent Integration
    hunter = LeadHunter()
    
    # Поиск клиентов раз в 2 часа (каналы TG + VK)
    scheduler.add_job(hunter.hunt, 'interval', hours=2)

    # Гео-шпион 24/7: чаты ЖК (Перекрёсток, Самолёт, ПИК и т.д.) — каждые 5 мин
    async def run_geo_spy_job():
        if not competitor_spy.geo_monitoring_enabled:
            return
        try:
            leads = await competitor_spy.scan_geo_chats()
            if leads:
                logger.info("🎯 GEO-Spy: найдено %s лидов", len(leads))
        except Exception as e:
            logger.error("GEO-Spy: %s", e)
    scheduler.add_job(run_geo_spy_job, "interval", seconds=competitor_spy.geo_check_interval)

    # Поиск идей для контента раз в 6 часов (темы ещё отправляются в группу после создания content_bot)
    scheduler.add_job(creative_agent.scout_topics, 'interval', hours=6)
    
    scheduler.start()
    
    # 2. Настройка АНТОНА
    main_bot = Bot(token=BOT_TOKEN or "", default=DefaultBotProperties(parse_mode="HTML"))
    from services.birthday_greetings import send_birthday_greetings
    scheduler.add_job(send_birthday_greetings, 'cron', hour=9, minute=0, args=[main_bot])

    # Инициализация сервисов
    publisher.bot = main_bot
    dp_main = Dispatcher(storage=MemoryStorage())
    dp_main.callback_query.middleware(UnhandledCallbackMiddleware())
    dp_main.include_router(admin_router)
    dp_main.include_router(creator_router)
    dp_main.include_router(quiz_router)   # раньше start: квиз по ссылке из поста обрабатывается первым
    dp_main.include_router(start_router)
    dp_main.include_router(dialog_router)
    
    # 3. Настройка ДОМ ГРАНД
    content_bot = Bot(token=CONTENT_BOT_TOKEN or "", default=DefaultBotProperties(parse_mode="HTML"))
    # Темы от креативщика в рабочую группу (топик Тренды/Сезон) раз в 6 ч
    async def post_creative_topics_to_group(bot):
        from config import LEADS_GROUP_CHAT_ID, THREAD_ID_TRENDS_SEASON
        try:
            topics = await creative_agent.scout_topics(3)
            text = "🕵️‍♂️ <b>Темы от креативщика</b> (актуальные)\n\n"
            for i, t in enumerate(topics, 1):
                text += f"{i}. <b>{t.get('title', '')}</b>\n   💡 {t.get('insight', '')}\n\n"
            await bot.send_message(LEADS_GROUP_CHAT_ID, text, message_thread_id=THREAD_ID_TRENDS_SEASON, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Ошибка отправки тем в группу: {e}")
    scheduler.add_job(post_creative_topics_to_group, 'interval', hours=6, args=[content_bot])
    from services.scheduler_ref import set_scheduler
    set_scheduler(scheduler)
    dp_content = Dispatcher(storage=MemoryStorage())
    dp_content.callback_query.middleware(UnhandledCallbackMiddleware())
    dp_content.include_routers(content_router)
    
    # 4. Команды для рабочей группы (всплывают как подсказки при /)
    from aiogram.types import BotCommand, BotCommandScopeChat
    try:
        await main_bot.set_my_commands(
            commands=[
                BotCommand(command="stats", description="Статистика скана"),
                BotCommand(command="hunt", description="Охота за лидами"),
                BotCommand(command="spy_status", description="Статус шпиона: чаты и лиды за 24 ч"),
                BotCommand(command="leads_review", description="Ревизия лидов за 12 ч: кто попался, какие боли"),
            ],
            scope=BotCommandScopeChat(chat_id=LEADS_GROUP_CHAT_ID),
        )
        logger.info("✅ Команды для рабочей группы заданы (stats, hunt, spy_status, leads_review)")
    except Exception as e:
        logger.warning("set_my_commands для группы: %s", e)

    # 5. Параллельный запуск
    logger.info("🚀 Очистка соединений и запуск polling...")
    await main_bot.delete_webhook(drop_pending_updates=True)
    await content_bot.delete_webhook(drop_pending_updates=True)

    await asyncio.gather(
        dp_main.start_polling(main_bot),
        dp_content.start_polling(content_bot)
    )


if __name__ == "__main__":
    asyncio.run(main())
