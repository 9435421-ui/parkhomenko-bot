# ================================================================
# ПАТЧ для main.py — интеграция scout_discovery
# Добавить в 3 места:
# ================================================================

# ── МЕСТО 1: импорты (в блок импортов вверху файла) ──────────────
import schedule
import threading
import time
from scout_discovery import run_discovery   # <-- добавить эту строку

# ── МЕСТО 2: задача в планировщике (рядом с post_scheduler) ──────
def discovery_job():
    """Запускается ночью — ищет новые жилые паблики ЖК в VK."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("🔍 Запуск discovery жилых пабликов...")
    stats = run_discovery()
    logger.info(
        f"Discovery завершён: удалено {stats['removed']}, "
        f"добавлено {stats['added']}, найдено {stats['found']}"
    )

# ── МЕСТО 3: регистрация в schedule (после строки с post_scheduler) ──
# Уже есть:
#   schedule.every().day.at("12:00").do(post_scheduler)
# Добавить под ней:
schedule.every().day.at("03:00").do(discovery_job)

# ── МЕСТО 4 (опционально): команда /run_discovery для ручного запуска ──
@bot.message_handler(commands=["run_discovery"])
def cmd_run_discovery(message):
    """Запуск discovery вручную (только для админа)."""
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
    if message.from_user.id != ADMIN_ID:
        return
    bot.send_message(message.chat.id, "🔍 Запускаю поиск жилых пабликов ЖК...")
    stats = run_discovery()
    bot.send_message(
        message.chat.id,
        f"✅ Discovery завершён:\n"
        f"🗑 Удалено конкурентов: {stats['removed']}\n"
        f"🔎 Найдено групп: {stats['found']}\n"
        f"✅ Добавлено новых: {stats['added']}\n"
        f"❌ Конкурентов пропущено: {stats['skipped_competitor']}\n"
        f"♻️ Уже были в БД: {stats['skipped_exists']}"
    )
