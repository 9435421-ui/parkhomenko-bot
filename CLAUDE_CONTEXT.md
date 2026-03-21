# ТЕРИОН — контекст проекта для Claude

## Суть проекта
CRM-бот для компании по согласованию перепланировок квартир (Москва).
Владелец: Юлия Пархоменко.
Бот ищет лидов в VK и Telegram, ведёт квиз-воронку, публикует контент, анализирует конкурентов.

## Репозиторий
GitHub: https://github.com/9435421-ui/parkhomenko-bot
Сервер: /root/PARKHOMENKO_BOT/
Стек: Python 3.11, Aiogram 3.x, Telethon, APScheduler, aiohttp, SQLite/aiosqlite, YandexGPT, Router AI

## Ключевые файлы
| Файл | Назначение | Статус |
|------|-----------|--------|
| `main.py` | Точка входа, два бота + scheduler | ✅ с Discovery задачей |
| `bot_spy.py` | Демон шпиона (Telethon + APScheduler, БЕЗ aiogram) | ✅ с start/stop БД |
| `vk_spy.py` | Автономный VK-шпион (aiohttp, без Telethon) | ✅ готов к запуску |
| `services/scout_parser.py` | Парсер TG+VK, VK API реализован | ✅ TG чаты из БД, горячие лиды в 811 |
| `session_manager.py` | Единый менеджер Telethon-сессии | ✅ исправлен |
| `config.py` | Все переменные окружения | ⚠️ дубль NOTIFICATIONS_CHANNEL_ID |
| `database/db.py` | SQLite + WAL mode | ✅ исправлен |
| `watchdog.py` | Самовосстановление процессов | ✅ исправлен |
| `handlers/` | start, quiz, dialog, admin, content, invest, vk_publisher, sales_agent | ✅ admin: голосовые интервью |
| `services/lead_hunter/` | hunter.py с Discovery + scheduler, analyzer.py, discovery.py | ✅ TG Discovery добавлен |
| `utils/yandex_gpt.py` | YandexGPT интеграция | ✅ исправлен |
| `agents/` | content_agent, creative_agent, image_agent, viral_hooks_agent, content_repurpose_agent | ✅ расширенная система агентов |

## Имя Telethon-сессии
`anton_scout` — основная сессия для парсинга и Discovery.
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

## Новые компоненты (март 2026)

### Агенты (agents/)
- `content_agent.py` — генерация контента
- `creative_agent.py` — креативные решения
- `image_agent.py` — генерация изображений
- `viral_hooks_agent.py` — вирусные хуки для постов
- `content_repurpose_agent.py` — repurposing контента

### Сервисы (services/)
- `competitor_spy.py` — анализ конкурентов
- `geospy.py` — гео-аналитика
- `geo_discovery.py` — гео-дискавери
- `image_generator.py` — генератор изображений
- `lead_service.py` — сервис лидов
- `publisher.py` — публикация контента
- `sales_reminders.py` — напоминания продаж
- `vk_service.py` — VK интеграции
- `voice_transcribe.py` — транскрибация голосовых
- `yandex_rag.py` — Yandex RAG система

### Обработчики (handlers/)
- `sales_agent.py` — агент продаж
- `vk_publisher.py` — публикация в VK
- `max_uploader.py` — загрузка в MAX.ru
- `creator.py` — креатор контента
- `main_bot.py` — основной бот

## Исправленные баги (март 2026, обновлено 22 марта)
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
14. ✅ quiz.py — новая квиз-воронка с 8 шагами, обработка планов, финальные сообщения по времени суток
15. ✅ scout_parser.py — чтение VK групп из БД (WHERE platform='vk' AND is_active=1)
16. ✅ scout_parser.py — экстрактор ID группы из link (club225569022 → 225569022)
17. ✅ scout_parser.py — реальная реализация _get_vk_posts() с VK API
18. ✅ scout_parser.py — реальная реализация _get_vk_comments() с VK API
19. ✅ bot_spy.py — добавлены вызовы await self.parser.start/stop()
20. ✅ hunter.py — интеграция Discovery в основной цикл hunt()
21. ✅ LeadHunter — новый метод run_discovery() для поиска новых VK групп
22. ✅ Планировщик — задача запуска Discovery раз в сутки (bot_anton.py, main.py)
23. ✅ Метод parse_vk → scan_vk_groups в hunter.py
24. ✅ База данных в scan_vk_groups — использование await db.get_connection()
25. ✅ Символ стрелки → в handlers/start.py заменён на текстовую стрелку ->
26. ✅ content_bot.py — исправлен синтаксис fstring в create_plan_posts (строка ~1468)
26. ✅ admin.py — реализована обработка голосовых сообщений (интервью) с отправкой черновиков в группу.
27. ✅ scout_parser.py — реализовано сканирование TG чатов из БД с сохранением лидов и отправкой горячих в топик 811.
28. ✅ hunter.py — добавлен метод run_tg_discovery для автоматического поиска чатов в Telegram.
29. ✅ deploy.sh — создан скрипт для деплоя файлов Жюля на сервер.

## Открытые задачи
- 🟡 ADMIN_ID в .env = placeholder, нужно заменить на реальный ID
- 🟡 Телеграм-сессия: код авторизации не приходит (пауза)
- 🟠 admin.py — некоторые кнопки меню всё ещё без обработчиков
- 🟠 Миграции БД — разные пути к файлу БД
- 🔵 Настройка контент-плана (следующий этап)

## Следующий шаг после шпиона
Настройка контент-агента и расписания публикаций.

## Проектные брифы (история разработки)

### BRIEF_бот_консультант.md (10-11 января 2026)
**Цель:** Создать Telegram-бота для автоматизации первичных консультаций по перепланировкам квартир.
**Ключевые достижения:**
- Стандартизация базы знаний (83 документа)
- Исправление критических багов (повторы, меню после квиза)
- Многократная итерация промпта для диалогового режима
- 8-шаговый квиз для сбора заявок
- Интеграция с YandexGPT и RAG

### BRIEF_перепланировки.md (январь 2026)
**Цель:** ИИ-консультант по перепланировкам + Telegram-канал.
**Ключевые элементы:**
- Роль ИИ-консультанта: понимание ситуации, объяснение, ведение к консультации
- База знаний: нормативка, FAQ, сценарии диалогов
- Связка "канал → бот → деньги"
- Техническая основа: Python + TeleBot + YandexGPT

### BRIEF_22012026_финализация_и_запуск_parkhomenko_bot.md (22 января 2026)
**Цель:** Перейти от технической настройки к публикации эталонного контента.
**Ключевые задачи:**
- Валидация новой структуры
- Первый "Чистый Прогон" контента
- Тест ImageAgent
- Подготовка Автопостинга

### BRIEF_agents_map_pereplanirovki.md (январь 2026)
**Цель:** Карта ИИ-агентов вокруг проекта перепланировок.
**Агенты:**
- Антон (перепланировки) - DIALOG, QUICK, QUIZ режимы
- Content Agent - ведение канала
- Agent парсинга и привлечения
- Agent личных консультаций
- Agent лендинга

### BRIEF_content_agent_channel_pereplanirovki.md (12 января 2026)
**Цель:** Подготовка документации для ИИ-контент-агента.
**Типы контента:**
- Образовательные посты
- Кейсы "было/стало"
- Мифы и страшилки
- Новости по теме
- Праздничные посты

### BRIEF_21_января_2026.md (21 января 2026)
**Цель:** Доработка квиза и критических задач.
**Ключевые задачи:**
- Добавление полей house_material и commercial_purpose
- Исправление обработки "да" на доп. контакт
- Приоритизация задач по UX
- Проверка Content Agent

### BRIEF_утро_бот_24_01.md (24 января 2026)
**Цель:** Аккуратная доработка консультанта/квиза.
**Принципы работы:**
- Мелкие, проверяемые шаги через VS Code-агента
- Только маленькие задачи, затрагивающие ограниченный участок кода
- Одна задача = один чёткий промпт → агент вносит изменения → проверка diff/куска кода

## Текущий статус (март 2026)
**Проект:** ТЕРИОН (ранее parkhomenko-bot)
**Цель:** CRM-бот для компании по согласованию перепланировок квартир
**Техническое состояние:** ✅ Рабочий, активно развивается
**Активные компоненты:**
- VK-шпион (автономный)
- Основной бот с квизом
- Контент-агент
- Система лидов
**Следующий этап:** Настройка контент-плана и расписания публикаций
