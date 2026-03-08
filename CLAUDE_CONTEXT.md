# ТЕРИОН — контекст проекта для Claude

## Суть проекта
CRM-бот для компании по согласованию перепланировок квартир (Москва).
Владелец: Юлия Пархоменко.
Бот ищет лидов в VK и Telegram, ведёт квиз-воронку, публикует контент.

## Репозиторий
GitHub: https://github.com/9435421-ui/parkhomenko-bot
Сервер: /root/PARKHOMENKO_BOT/
Стек: Python 3.11, Aiogram 3.x, Telethon, APScheduler, aiohttp, SQLite/aiosqlite

## Ключевые файлы
| Файл | Назначение | Статус |
|------|-----------|--------|
| `main.py` | Точка входа, два бота + scheduler | ✅ рабочий |
| `bot_spy.py` | Демон шпиона (Telethon + APScheduler, БЕЗ aiogram) | ✅ исправлен |
| `vk_spy.py` | Автономный VK-шпион (aiohttp, без Telethon) | ✅ готов к запуску |
| `services/scout_parser.py` | Парсер TG+VK, async for исправлен | ✅ исправлен |
| `session_manager.py` | Единый менеджер Telethon-сессии | ✅ исправлен |
| `config.py` | Все переменные окружения | ⚠️ дубль NOTIFICATIONS_CHANNEL_ID |
| `database/db.py` | SQLite + WAL mode | ✅ исправлен |
| `watchdog.py` | Самовосстановление процессов | ✅ исправлен |
| `handlers/` | start, quiz, dialog, admin, content, invest, vk_publisher | 🟡 квиз не дописан |
| `services/lead_hunter/` | hunter.py, analyzer.py, discovery.py | ✅ исправлен |
| `utils/yandex_gpt.py` | YandexGPT интеграция | ✅ исправлен |
| `agents/content_agent.py` | Контент-агент (async) | ✅ исправлен |

## Имя Telethon-сессии
`anton_parser` — единое во всём проекте.
Файл: `anton_parser.session` — в .gitignore, не коммитить!
Статус: ⚠️ авторизация не пройдена (проблемы с получением кода)

## Текущий фокус
VK-шпион (`vk_spy.py`) работает автономно — без Telethon-сессии.
Карточки лидов приходят в Telegram с кнопками:
- ✅ Взять в работу
- ❌ Не наш клиент
- 🔗 Открыть в VK
- 📋 Квиз

## .env — ключевые переменные
```
BOT_TOKEN=...
CONTENT_BOT_TOKEN=...
API_ID=...
API_HASH=...
PHONE=+7...
VK_TOKEN=vk1.a....
LEADS_GROUP_CHAT_ID=-100...
THREAD_ID_HOT_LEADS=811
SCOUT_VK_GROUPS=225569022,...
VK_SCAN_INTERVAL=1800
ADMIN_ID=...           # ← было 'your_admin_user_id_here', нужно исправить!
JULIA_USER_ID=...
VK_QUIZ_LINK=https://t.me/Parkhovenko_i_kompaniya_bot?start=quiz
```

## Команды запуска на сервере
```bash
# VK-шпион (приоритет сейчас)
screen -S vk_spy
cd /root/PARKHOMENKO_BOT
python vk_spy.py

# Основной бот
screen -S main_bot
python main.py

# Авторизация Telethon (когда понадобится)
python session_manager.py
python session_manager.py --reset  # если сессия сломана
```

## Исправленные баги (март 2026)
1. ✅ Утечки секретов (fix_session.py, test_spy.py, scanbot.session)
2. ✅ Импорты роутеров в main.py / handlers/__init__.py
3. ✅ set_content_bot в bot_config.py
4. ✅ hunter_standalone импорт убран из bot_spy.py
5. ✅ Конфликт токенов — bot_spy.py больше не запускает aiogram
6. ✅ async for в scout_parser.py (был синхронный for — возвращал [])
7. ✅ get_last_scan_report() возвращает строку а не dict
8. ✅ yandex_gpt.py — system_prompt передавался неверно
9. ✅ content_agent.py — синхронный requests заменён на async
10. ✅ router_ai.py — неверный base_url исправлен
11. ✅ knowledge_base.py — неверный docs_dir исправлен
12. ✅ image_agent.py — заглушки заменены на реальные вызовы
13. ✅ WAL mode + busy_timeout в database/db.py

## Открытые задачи
- 🟡 ADMIN_ID в .env = placeholder, нужно заменить на реальный ID
- 🟡 Телеграм-сессия: код авторизации не приходит (пауза)
- 🟠 Квиз в quiz.py — написаны только 2 из 8 состояний FSM
- 🟠 admin.py — кнопки без обработчиков
- 🟠 Миграции БД — разные пути к файлу БД
- 🔵 Настройка контент-плана (следующий этап)

## Следующий шаг после шпиона
Настройка контент-агента и расписания публикаций.
