"""
Основной бот ТЕРИОН - aiogram 3.x + Content Factory.
Запуск ДВУХ ботов с РАЗДЕЛЬНЫМИ Dispatchers:
- main_bot (АНТОН): консультант по перепланировкам
- content_bot (ДОМ ГРАНД): контент и посты

Единый источник истины: Bot и Dispatcher создаются только здесь.
Остальные модули получают бота через utils.bot_config.get_main_bot() или из контекста (message.bot, callback.bot).
Неубивайка: lock bot.lock, один процесс на инстанс.
"""
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, CONTENT_BOT_TOKEN, LEADS_GROUP_CHAT_ID
from handlers import register_all_handlers, content_router
from database import db
from utils import kb
from middleware.logging import UnhandledCallbackMiddleware
from services.scout_parser import ScoutParser
from agents.creative_agent import creative_agent
from services.lead_hunter.hunter import LeadHunter
from services.competitor_spy import competitor_spy
from services.publisher import publisher
from services.image_generator import image_generator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DbLogHandler(logging.Handler):
    """Кастомный обработчик логов для записи в БД."""
    def emit(self, record):
        if record.levelno >= logging.ERROR:
            try:
                msg = self.format(record)
                stack = record.exc_text if record.exc_info else None
                asyncio.create_task(db.add_system_log(record.levelname, record.name, msg, stack))
            except:
                pass

# Добавляем обработчик в корневой логгер
logging.getLogger().addHandler(DbLogHandler())

# Аудит: видим PID, чтобы убедиться, что процесс не запускается дважды
print(f"DEBUG: Started process with PID {os.getpid()}")

LOCK_FILE = Path(__file__).resolve().parent / "bot.lock"


def _acquire_lock() -> None:
    """Если lock-файл существует — завершить старый процесс по PID, затем записать текущий PID."""
    if LOCK_FILE.exists():
        try:
            raw = LOCK_FILE.read_text().strip()
            old_pid = int(raw)
        except (ValueError, OSError):
            old_pid = None
        if old_pid and old_pid != os.getpid():
            try:
                os.kill(old_pid, signal.SIGTERM)
                logger.warning("Завершён предыдущий процесс main.py (PID %s)", old_pid)
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.warning("Не удалось завершить старый процесс %s: %s", old_pid, e)
        try:
            LOCK_FILE.unlink()
        except OSError:
            pass
    LOCK_FILE.write_text(str(os.getpid()))


def _release_lock() -> None:
    """Удалить lock-файл при корректном выходе."""
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
            logger.info("Lock bot.lock снят")
    except OSError as e:
        logger.warning("Не удалось удалить bot.lock: %s", e)


async def main():
    logger.info("🎯 Запуск ЭКОСИСТЕМЫ TERION...")
    _acquire_lock()
    # Один Dispatcher на токен, один start_polling на токен — только здесь

    # 1. Единая инициализация ресурсов
    await db.connect()
    await kb.index_documents()

    # 2. Один раз создаём экземпляры ботов (далее используем их везде, включая проверку связей)
    main_bot = Bot(token=BOT_TOKEN or "", default=DefaultBotProperties(parse_mode="HTML"))
    content_bot = Bot(token=CONTENT_BOT_TOKEN or "", default=DefaultBotProperties(parse_mode="HTML"))
    from utils.bot_config import set_main_bot, set_content_bot
    set_main_bot(main_bot)
    set_content_bot(content_bot)
    publisher.bot = main_bot

    # 3. Проверка связей (те же экземпляры main_bot, content_bot — сессии не закрываем)
    logger.info("🔍 Проверка связей...")
    try:
        from config import CHANNEL_ID_TERION, CHANNEL_ID_DOM_GRAD, LEADS_GROUP_CHAT_ID
        from config import THREAD_ID_DRAFTS, THREAD_ID_CONTENT_PLAN, THREAD_ID_TRENDS_SEASON, THREAD_ID_LOGS
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
        try:
            await main_bot.get_chat(LEADS_GROUP_CHAT_ID)
            logger.info("✅ Рабочая группа: OK")
        except Exception as e:
            logger.error(f"❌ Рабочая группа: {e}")
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
        for thread_id, name in [
            (THREAD_ID_DRAFTS, "Черновики"),
            (THREAD_ID_CONTENT_PLAN, "Контент-план"),
            (THREAD_ID_TRENDS_SEASON, "Тренды/Сезон"),
            (THREAD_ID_LOGS, "Логи")
        ]:
            try:
                await main_bot.get_chat(LEADS_GROUP_CHAT_ID)
                logger.info(f"✅ Топик {name}: OK")
            except Exception as e:
                logger.error(f"❌ Топик {name}: {e}")
    except Exception as e:
        logger.error(f"Ошибка проверки связей: {e}")

    scheduler = AsyncIOScheduler()

    from services.publisher import Publisher
    poster = Publisher(main_bot)

    # Проверка и публикация по расписанию
    scheduler.add_job(poster.check_and_publish, "interval", minutes=10)
    scheduler.add_job(poster.check_and_publish, "cron", hour=12, minute=0)  # явно в 12:00

    # Lead Hunter & Creative Agent Integration
    hunter = LeadHunter()
    
    # Поиск клиентов каждые 30 минут (каналы TG + VK)
    scheduler.add_job(hunter.hunt, 'interval', minutes=30)

    # Инсайт недели: воскресенье, 18:00
    scheduler.add_job(hunter.generate_weekly_insight, 'cron', day_of_week='sun', hour=18, minute=0)
    
    # Поиск новых VK групп раз в сутки через Discovery
    scheduler.add_job(
        hunter.run_discovery,
        'interval',
        hours=24,
        id='vk_discovery',
        max_instances=1
    )

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
    # Задачи планировщика получают main_bot/content_bot аргументом, своих Bot() не создают
    from services.birthday_greetings import send_birthday_greetings
    scheduler.add_job(send_birthday_greetings, 'cron', hour=9, minute=0, args=[main_bot])

    # Единственные экземпляры Dispatcher в проекте; start_polling вызывается только ниже, по одному разу на каждый
    dp_main = Dispatcher(storage=MemoryStorage())
    dp_main.callback_query.middleware(UnhandledCallbackMiddleware())
    
    # Регистрация всех обработчиков через единую функцию
    register_all_handlers(dp_main)

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
                BotCommand(command="scan_chats", description="Сканер чатов: ID, название, участники (для добычи ID)"),
            ],
            scope=BotCommandScopeChat(chat_id=LEADS_GROUP_CHAT_ID),
        )
        logger.info("✅ Команды для рабочей группы заданы (stats, hunt, spy_status, leads_review)")
    except Exception as e:
        logger.warning("set_my_commands для группы: %s", e)

    # 5. Параллельный запуск (Force Webhook Clear + Conflict Retry + Graceful Shutdown)
    async def close_bot_sessions():
        """Закрыть сессии ботов и снять lock."""
        for name, bot in [("main_bot", main_bot), ("content_bot", content_bot)]:
            try:
                session = getattr(bot, "session", None)
                if session is None:
                    continue
                if getattr(session, "_connector", None) is not None:
                    await session.close()
                    logger.info("Сессия %s закрыта", name)
            except Exception as e:
                logger.warning("Ошибка закрытия сессии %s: %s", name, e)
        _release_lock()

    logger.info("🚀 Очистка webhook и запуск polling...")
    await main_bot.delete_webhook(drop_pending_updates=True)
    await content_bot.delete_webhook(drop_pending_updates=True)

    try:
        await asyncio.gather(
            dp_main.start_polling(main_bot, skip_updates=True),
            dp_content.start_polling(content_bot, skip_updates=True),
        )
    except asyncio.CancelledError:
        logger.info("Polling остановлен")
    finally:
        await close_bot_sessions()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
