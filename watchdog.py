"""
Watchdog — система самовосстановления (Self-Healing).
Автоматически перезапускает основной бот и шпиона при падении.
Записывает ошибки в базу данных.
"""
import asyncio
import subprocess
import sys
import logging
import os
import signal
import traceback
from datetime import datetime
import aiohttp

# Настройка логов
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("watchdog.log", encoding='utf-8')
    ]
)
logger = logging.getLogger("Watchdog")

# Фатальные ошибки, требующие паузы в 1 час
FATAL_PATTERNS = [
    "SessionPasswordNeededError",
    "FloodWaitError",
    "AuthKeyInvalidError",
    "AuthKeyUnregisteredError",
    "PhoneNumberInvalidError",
    "ApiIdInvalidError",
    "ApiIdPublishedFloodError"
]

# Процессы, за которыми следим
PROCESSES = {
    "main_bot": {
        "command": [sys.executable, "run_anton.py"],
        "restart_count": 0,
        "last_restart": None,
        "fatal_error": False
    },
    "lead_hunter": {
        "command": [sys.executable, "run_hunter.py"],
        "restart_count": 0,
        "last_restart": None,
        "fatal_error": False
    }
}

running_subprocesses = {}

async def notify_admin(message: str):
    """Отправка уведомления администратору в Telegram."""
    try:
        admin_id = os.getenv("ADMIN_ID")
        bot_token = os.getenv("BOT_TOKEN")  # Предполагаем, что есть BOT_TOKEN в .env
        if not admin_id or not bot_token:
            logger.warning("ADMIN_ID или BOT_TOKEN не заданы в .env, уведомление не отправлено")
            return
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": admin_id,
            "text": f"🚨 Watchdog Alert:\n{message}",
            "parse_mode": "Markdown"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    logger.info("✅ Уведомление отправлено администратору")
                else:
                    logger.error(f"❌ Ошибка отправки уведомления: {response.status}")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомления: {e}")

async def log_to_db(level, module, message, stack_trace=None):
    """Асинхронная запись лога в БД."""
    try:
        from database.db import db
        if not db.conn:
            await db.connect()
        await db.add_system_log(level, module, message, stack_trace)
    except Exception as e:
        logger.error(f"Не удалось записать лог в БД: {e}")

async def run_managed_process(name, config):
    """Запуск и мониторинг процесса."""
    while True:
        logger.info(f"🚀 Запуск процесса: {name}")
        await log_to_db("INFO", "Watchdog", f"Запуск процесса {name}")
        
        try:
            # Запускаем подпроцесс
            process = await asyncio.create_subprocess_exec(
                *config["command"],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            running_subprocesses[name] = process
            
            # Читаем stdout для логирования всех print()
            async def log_stdout(stdout_stream):
                while True:
                    line = await stdout_stream.readline()
                    if not line:
                        break
                    msg = line.decode().strip()
                    if msg:
                        logger.info(f"[{name}] {msg}")
            
            # Читаем stderr для логирования ошибок и обнаружения фатальных
            async def log_errors(stderr_stream):
                while True:
                    line = await stderr_stream.readline()
                    if not line:
                        break
                    err_msg = line.decode().strip()
                    if err_msg:
                        logger.error(f"[{name}] {err_msg}")
                        # Если это критическая ошибка (traceback), пишем в БД
                        if "Traceback" in err_msg or "Error" in err_msg:
                            await log_to_db("ERROR", name, err_msg)
                        
                        # Проверяем на фатальные ошибки сессии (сразу при обнаружении)
                        for pattern in FATAL_PATTERNS:
                            if pattern in err_msg:
                                config["fatal_error"] = True
                                logger.critical(f"🚨 Обнаружена фатальная ошибка: {pattern}")
                                await notify_admin(f"🚨 Критическая ошибка в {name}: {pattern}. Пауза 1 час.")
                                break

            asyncio.create_task(log_stdout(process.stdout))
            asyncio.create_task(log_errors(process.stderr))
            
            # Ждем завершения
            returncode = await process.wait()
            
            error_msg = f"Процесс {name} завершился с кодом {returncode}"
            logger.warning(error_msg)
            await log_to_db("WARNING", "Watchdog", error_msg)
            
        except Exception as e:
            error_msg = f"Ошибка при выполнении {name}: {e}"
            logger.error(error_msg)
            await log_to_db("CRITICAL", name, error_msg, traceback.format_exc())
        
        # Логика перезапуска
        config["restart_count"] += 1
        config["last_restart"] = datetime.now()
        
        # Проверяем на фатальные ошибки (сразу без накопления попыток)
        if config.get("fatal_error"):
            wait_time = 3600  # 1 час при фатальной ошибке
            logger.warning(f"⏳ Фатальная ошибка в {name}. Пауза {wait_time} сек.")
        else:
            wait_time = min(60, 5 * config["restart_count"])
        
        logger.info(f"⏳ Перезапуск {name} через {wait_time} сек (попытка {config['restart_count']})")
        await asyncio.sleep(wait_time)

async def main():
    logger.info("🛡️ Watchdog ТЕРИОН запущен.")
    
    # Регистрация сигналов для корректного завершения
    def handle_exit(sig, frame):
        logger.info(f"🛑 Получен сигнал {sig}. Завершение всех процессов...")
        for name, proc in running_subprocesses.items():
            try:
                proc.terminate()
                logger.info(f"✅ Процесс {name} завершен.")
            except:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    # Запускаем процессы последовательно с паузой, чтобы избежать конфликта при создании таблиц
    tasks = []
    for name, config in PROCESSES.items():
        task = asyncio.create_task(run_managed_process(name, config))
        tasks.append(task)
        if name == "main_bot":
            await asyncio.sleep(3)  # Пауза 3 секунды перед запуском Шпиона
    
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
