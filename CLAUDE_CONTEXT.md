# ГЕОРИС — контекст проекта для Claude

## Суть проекта
Мультиагентная система для компании по согласованию перепланировок квартир (Москва).
Владелец: Юлия Пархоменко.
Что делает система:
Бот-консультант «Антон» ведёт клиентов через квиз-воронку
Контент-бот публикует экспертный контент в TG, VK, Яндекс Дзен
VK-шпион ищет горячих лидов в жилых ЖК группах
Юлия управляет всем через диалог с ботом в Telegram (пишет задание → бот предлагает варианты → одобрение → публикация)

## Репозиторий
GitHub: https://github.com/9435421-ui/parkhomenko-bot
Сервер: 176.124.219.183, /root/PARKHOMENKO_BOT/
Стек: Python 3.11, Aiogram 3.x, Telethon, APScheduler, aiohttp, SQLite/aiosqlite, YandexGPT, Router AI, FFmpeg, Pillow

## Два активных бота
| Бот | Username | Роль |
|-----|----------|------|
| Антон | @Parkhovenko_i_kompaniya_bot | ИИ-консультант по перепланировкам |
| Дом Гранд | @domGrad_bot | Контент-бот бренда Дом Гранд |

## Каналы и группы
| ID | Назначение |
|----|------------|
| `-1003612599428` | TG канал ГЕОРИС |
| `-1002628548032` | TG канал Дом Гранд |
| `235569022` | VK группа |
| `-1003370698977` | LEADS_GROUP_CHAT_ID (рабочая группа лидов) |
| `THREAD_ID_DRAFTS=85` | Топик черновиков |
| `THREAD_ID_HOT_LEADS=811` | Топик горячих лидов |
| `ADMIN_ID=8438024806` | Юлия |

## Ключевые файлы
| Файл | Назначение | Статус |
|------|-----------|--------|
| `bot_anton.py` | Основной бот-консультант (aiogram 3.x) | ✅ активный |
| `bot_spy.py` | Демон шпиона (Telethon + ScoutParser) | ✅ активный |
| `handlers/content_bot.py` | Контент-бот (~2600+ строк), диалог с Юлией | ✅ активный |
| `run_content_bot.py` | Запуск контент-бота + APScheduler | ✅ активный |
| `services/scout_parser.py` | Парсер TG+VK, VK API реализован | ✅ TG чаты из БД, горячие лиды в 811 |
| `session_manager.py` | Единый менеджер Telethon-сессии | ✅ исправлен |
| `config.py` | Все переменные окружения | ⚠️ дубль NOTIFICATIONS_CHANNEL_ID |
| `database/database.py` | SQLite + WAL mode | ✅ исправлен |
| `handlers/video_handler_v2.py` | FSM-обработчик команды /video | ✅ готов |
| `services/video_editor.py` | FFmpeg обработка видео | ✅ готов |
| `services/video_publisher.py` | Публикация видео в TG/VK | ✅ готов |
| `services/content_generator.py` | Генерация текстов (YandexGPT) | ✅ готов |
| `utils/yandex_gpt.py` | YandexGPT интеграция | ✅ исправлен |
| `agents/` | content_agent, creative_agent, image_agent, viral_hooks_agent, content_repurpose_agent | ✅ активны |

## Видео-модуль (добавлен март 2026)
Команда `/video` — полный цикл:
Юлия загружает видео в бот
FFmpeg: шумоподавление, удаление пауз, ускорение 1.2x
Ватермарк ГЕОРИС (шрифт Roboto-Bold.ttf)
YandexGPT генерирует текст поста
Публикация в TG (ГЕОРИС + Дом Гранд) и VK
Дзен-бот автоматически публикует в Яндекс Дзен

Папочная структура видео:
```
videos/
├── raw/          # исходники
├── processed/    # обработанные
├── published/    # опубликованные
├── failed/       # ошибки
├── thumbnails/   # превью
└── watermarks/   # ватермарки
```

Таблица БД: `video_reports` — хранит статусы и метаданные видео.
Статус: ✅ готов, ожидает первого живого теста

## Контент-бот — диалоговый режим
Юлия пишет задание в Telegram (например: "подготовь серию постов на 5 дней по перепланировкам в маленьких квартирах с газовой плитой"), бот:
Генерирует черновики через YandexGPT
Предлагает варианты с кнопками одобрения
После одобрения публикует по расписанию

Ключевые механизмы:
APScheduler: автопубликация каждую минуту (проверка БД)
Генерация изображений: Flux.2-pro через Router AI (`black-forest-labs/flux.2-pro`, base64)
Callback data: MD5 hash-ключи в `bot_settings` (стабильность при длинных данных)
`prepare_dzen_draft` + колонка `dzen_status` для Яндекс Дзен
9 экспертных постов загружены в `content_plan`
Черновики → топик 85, горячие лиды → топик 811

## Имя Telethon-сессии
`anton_scout` — основная сессия для парсинга и Discovery.
Файл: `anton_parser.session` — ⚠️ НЕ коммитить (но сейчас лежит в репо — нужно удалить!)
Статус: авторизована под аккаунтом @Ylya_dorogaya

## .env — ключевые переменные
```
BOT_TOKEN=...
CONTENT_BOT_TOKEN=...
API_ID=...
API_HASH=...
PHONE=+7...
VK_TOKEN=vk1.a....           # VK Standalone app ID: 54491024, scope: wall,groups,photos,offline
LEADS_GROUP_CHAT_ID=-1003370698977
THREAD_ID_HOT_LEADS=811
THREAD_ID_DRAFTS=85
SCOUT_VK_GROUPS=235569022,...
VK_SCAN_INTERVAL=1800
ADMIN_ID=8438024806
JULIA_USER_ID=...
VK_QUIZ_LINK=https://t.me/Parkhovenko_i_kompaniya_bot?start=quiz
```

⚠️ Важно: `override=True` в `load_dotenv()` — обязательно, иначе конфликт переменных.

## Команды запуска на сервере
```bash
# Основной бот
systemctl start anton_bot   # или: python bot_anton.py

# Контент-бот
systemctl start domgrad_bot  # или: python run_content_bot.py
# ⚠️ описание сервиса ещё читается как "TERION Content Bot" — нужно обновить

# Шпион
screen -S bot_spy
python bot_spy.py

# Деплой обновлений
cd /root/PARKHOMENKO_BOT && git pull --rebase
```

## Известные баги (не исправлены)
🔴 `get_main_bot()` возвращает None в контексте scout_parser → уведомления в топик 811 не работают
🔴 Telethon SQLite session: "database is locked" при параллельном доступе
🟠 Дублирующийся обработчик `pub_all:` в `content_bot.py`
🟠 `edit_draft` отправляет новое сообщение вместо редактирования inline
🟠 Бесконечная публикация (спам одобренных постов) — временно исправлен bulk-update статусов, root cause не найден
🟡 Описание systemd сервиса контент-бота: ещё читается "TERION Content Bot"
🟡 `anton_parser.session` лежит в репо (нужно удалить и добавить в .gitignore)

## Дорожная карта (приоритеты)
### Сейчас (конец марта 2026)
🎯 Первый живой тест команды `/video`
🎯 Настройка контент-плана на следующую неделю

### Ближайшее (апрель 2026)
🔵 Дзен синхронизация — тест
🔵 Дизайн/брендинг VK сообщества
🔵 Команда `/edit_post` для редактирования черновиков
🔵 Настройка шпиона (TG Discovery, фильтры лидов)
🔵 Реклама (настройка после шпиона)

### Ожидает регистрации компании
⏳ MAX.ru — интеграция публикаций (токен получим после регистрации ООО)
Файл: `handlers/max_uploader.py` — уже есть заготовка

## Структура проекта
```
/root/PARKHOMENKO_BOT/
├── bot_anton.py              # Консультант Антон
├── bot_spy.py                # VK/TG шпион
├── run_content_bot.py        # Контент-бот + APScheduler
├── config.py
├── handlers/
│   ├── content_bot.py        # ~2600+ строк, основной контент-обработчик
│   ├── video_handler_v2.py   # FSM /video
│   ├── admin.py              # Голосовые интервью, кнопки лидов
│   ├── quiz.py               # 8-шаговый квиз
│   ├── dialog.py             # RAG диалог
│   ├── sales_agent.py
│   ├── vk_publisher.py
│   └── max_uploader.py       # заготовка, ждёт токен
├── services/
│   ├── scout_parser.py       # TG+VK парсер
│   ├── video_editor.py       # FFmpeg
│   ├── video_publisher.py    # TG/VK публикация видео
│   ├── content_generator.py  # YandexGPT тексты
│   ├── publisher.py          # Общий публикатор
│   ├── vk_token_manager.py   # Мониторинг VK токена (6ч)
│   ├── lead_hunter/
│   │   ├── hunter.py
│   │   ├── discovery.py
│   │   └── outreach.py
│   └── ...
├── agents/
│   ├── content_agent.py
│   ├── creative_agent.py
│   ├── image_agent.py
│   ├── viral_hooks_agent.py
│   └── content_repurpose_agent.py
├── database/
│   └── database.py           # SQLite WAL, таблицы: video_reports, content_plan, bot_settings, ...
├── knowledge_base/           # 83+ документа по нормативке
├── utils/
│   ├── yandex_gpt.py
│   ├── router_ai.py          # Flux.2-pro для изображений
│   └── knowledge_base.py
└── videos/                   # raw/processed/published/failed/thumbnails/watermarks/
```

## Проектные брифы (история разработки)
январь 2026 — Бот-консультант Антон, RAG, 8-шаговый квиз, YandexGPT
январь 2026 — Контент-агент, типы контента, связка канал→бот→деньги
22 января 2026 — Первый чистый прогон контента, ImageAgent, автопостинг
март 2026 (до 22) — VK-шпион, TG Discovery, очистка 48 файлов (17,288 строк), исправлено 31 баг
март 2026 (после 22) — Ребрендинг ТЕРИОН→ГЕОРИС (60+ файлов), видео-модуль, Flux.2-pro, MD5 callbacks, Дзен

## Текущий статус (29 марта 2026)
Проект: ГЕОРИС v2.0 (Video Production)
Техническое состояние: ✅ Production Ready
Активные компоненты:
✅ Бот-консультант Антон (квиз, RAG, диалог)
✅ Контент-бот с диалоговым управлением (Юлия пишет → бот генерирует → публикует)
✅ VK-шпион (автономный, горячие лиды в топик 811)
✅ Видео-модуль (FFmpeg, ватермарк, /video команда)
✅ Автопубликация (APScheduler, каждую минуту)
✅ Публикация: TG + VK + Яндекс Дзен
⏳ MAX.ru — ждёт регистрации компании
VK_SCAN_INTERVAL=1800
ADMIN_ID=...           # ← было 'your_admin_user_id_here', нужно исправить!
JULIA_USER_ID=...
VK_QUIZ_LINK=https://t.me/Parkhovenko_i_kompaniya_bot?start=quiz
```

## Команды запуска на сервере
```bash
# Основной бот (заменил main.py)
screen -S bot_anton
cd /root/PARKHOMENKO_BOT
python bot_anton.py

# Шпион (заменил bot_spy.py)
screen -S bot_spy
python bot_spy.py

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
- `vk_token_manager.py` — менеджер VK токенов
- `voice_transcribe.py` — транскрибация голосовых
- `yandex_rag.py` — Yandex RAG система
- `birthday_greetings.py` — поздравления с днем рождения

### Обработчики (handlers/)
- `sales_agent.py` — агент продаж
- `vk_publisher.py` — публикация в VK
- `max_uploader.py` — загрузка в MAX.ru
- `creator.py` — креатор контента
- `main_bot.py` — основной бот

### LeadHunter компоненты
- `hunter.py` — основной охотник за лидами
- `analyzer.py` — анализатор лидов
- `discovery.py` — поиск новых групп
- `outreach.py` — outreach функционал
- `database.py` — база данных лидов

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
27. ✅ admin.py — реализована обработка голосовых сообщений (интервью) с отправкой черновиков в группу.
28. ✅ scout_parser.py — реализовано сканирование TG чатов из БД с сохранением лидов и отправкой горячих в топик 811.
29. ✅ hunter.py — добавлен метод run_tg_discovery для автоматического поиска чатов в Telegram.
30. ✅ deploy.sh — создан скрипт для деплоя файлов Жюля на сервер.
31. ✅ Проект очищен от 48 дублирующих и устаревших файлов (17,288 строк кода)

## Очистка проекта (22 марта 2026)
Удалено **48 файлов** (17,288 строк кода) — дубликаты, старые версии, сломанные БД:
- ❌ `main.py` → заменен на `bot_anton.py`
- ❌ `vk_spy.py` → функционал в `bot_spy.py`
- ❌ `content_bot.py` → функционал в `handlers/content_bot.py`
- ❌ `auto_poster.py` → заменен на `services/publisher.py`
- ❌ `quiz.py` → функционал в `handlers/quiz.py`
- ❌ `scout_parser.py` → функционал в `services/scout_parser.py`
- ❌ `watchdog.py` → функционал интегрирован в основные боты
- ❌ `content_bot_mvp/` — полная директория дубликата
- ❌ `hunter_standalone/` — устаревший модуль
- ❌ `jules_extracted/` — извлеченные файлы
- ❌ `Жюль/` — директория дубликата
- ❌ Сломанные файлы БД (.broken, .old, .shm)

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
**Проект:** ГЕОРИС (ранее parkhomenko-bot)
**Цель:** CRM-бот для компании по согласованию перепланировок квартир
**Техническое состояние:** ✅ Рабочий, активно развивается
**Активные компоненты:**
- VK-шпион (автономный)
- Основной бот с квизом
- Контент-агент
- Система лидов
**Следующий этап:** Настройка контент-плана и расписания публикаций
