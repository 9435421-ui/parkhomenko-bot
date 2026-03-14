# Аудит архитектуры запуска (TelegramConflictError)

## Правила

- **Bot и Dispatcher** создаются **только в main.py**.
- **start_polling()** вызывается **только в main.py** (два раза: для main_bot и content_bot).
- **asyncio.run()** в продакшене — только в main.py при `if __name__ == "__main__"`.
- Остальные модули получают бота через **utils.bot_config.get_main_bot()** или из контекста (**message.bot**, **callback.bot**).
- Задачи **AsyncIOScheduler** получают экземпляр бота аргументом (main_bot/content_bot), своих Bot() не создают.

## Где создаётся Bot(token=...)

| Файл | Назначение |
|------|------------|
| **main.py** | Единственное место для продакшена: main_bot, content_bot. |
| services/lead_hunter/hunter.py | Fallback, только если get_main_bot() вернул None (запуск hunt вне main, например run_hunt_once). |
| run_all.py, vk_parser.py, chat_parser.py, test_logs.py | Скрипты/альтернативные точки входа. **Не запускать одновременно с main.py.** |

## start_polling()

- **main.py** — dp_main.start_polling(main_bot), dp_content.start_polling(content_bot).
- **run_all.py** — свой polling; при наличии bot.lock скрипт завершается с ошибкой.

## Импорты без побочных эффектов

- **LeadHunter**, **ScoutParser**, **CreativeAgent**: при импорте создаются только объекты классов (scout_parser = ScoutParser(), creative_agent = CreativeAgent()). Никаких Bot(), start_polling() или asyncio.run() на уровне модуля нет.

## Проверка двойного запуска

- В начале main.py выводится **DEBUG: Started process with PID {os.getpid()}**. Если в логах два разных PID для одного инстанса — процесс запущен дважды.
- **bot.lock** гарантирует один процесс: при старте старый PID из lock завершается (SIGTERM), в lock записывается текущий PID.
