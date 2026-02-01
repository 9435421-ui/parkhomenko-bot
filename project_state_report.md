# Отчет о фактическом состоянии проекта ТОРИОН

**Дата:** 2026-02-01
**Объект:** Инвентаризация структуры и процессов

---

## 1. Структура проекта (ROOT)

Фактическая структура (основные узлы):
- `content_bot_mvp/` — автономный сервис контент-бота (@domGrad_bot)
- `database/` — модули работы с БД (root)
- `handlers/` — обработчики основного бота (@torion_bot)
- `keyboards/` — UI компоненты
- `knowledge_base/` — документы для RAG
- `services/` — внешние интеграции (VK, Lead Service)
- `utils/` — утилиты (YandexGPT Client, Knowledge Base)
- `mini_app/` — Telegram Mini App (Invest Calculator)

### Полное дерево проекта (без venv):
```
.
./бот_по_перепланировкам
./бот_по_перепланировкам/knowledge_base
./auto_poster.py
./mini_app
./mini_app/index.html
./mini_app/README.md
./requirements.txt
./config
./knowledge_base
./BRIEF_перепланировки.md
./database.py
./migrations
./handlers
./handlers/dialog.py
./handlers/__init__.py
./handlers/start.py
./handlers/invest.py
./handlers/quiz.py
./docs
./kb_rag.py
./README.md
./DEPLOY.md
./utils
./utils/knowledge_base.py
./utils/__init__.py
./utils/yandex_gpt.py
./database
./database/models.py
./database/__init__.py
./database/db.py
./docker-compose.yml
./backup_db.py
./next_steps_recommendation.md
./start.sh
./full_check_bot_report.sh
./BRIEF_бот_консультант.md
./keyboards
./keyboards/__init__.py
./keyboards/main_menu.py
./BRIEF_content_agent_channel_pereplanirovki.md
./parkhomenko_bot.db
./content_bot_mvp
./content_bot_mvp/bot.pid
./content_bot_mvp/main.py
./bot.log
./project_state_report.md
./QUICKSTART.md
./config.py
./apply_migration.py
./functional_matrix.md
./run_bot.sh
./agents
./agents/image_agent.py
./Dockerfile
./BRIEF_agents_map_pereplanirovki.md
./bot_unified.py
./BRIEF_pereplanirovki.md
./main.py
./content_agent.py
./services
./services/__init__.py
./services/lead_service.py
./services/vk_service.py
./services/yandex_rag.py
```

## 2. Точки входа и активные процессы

### 2.1 Точки входа (Entry Points)
1. `content_bot_mvp/main.py` (telebot) — Контент-бот
2. `main.py` (aiogram) — Основной бот консультант
3. `bot_unified.py` (telebot) — Устаревшая или экспериментальная версия

### 2.2 Активные процессы (PIDs)
- **run_bot.sh** (PID: 13943) — скрипт мониторинга
- **content_bot_mvp/main.py** (PID: 14695) — активный процесс @domGrad_bot

## 3. Активные боты и токены

| Bot Name | Token Source | PID | Status |
| :--- | :--- | :--- | :--- |
| @domGrad_bot | `content_bot_mvp/.env` | 14695 | **ACTIVE** |
| @torion_bot | `.env` (TELEGRAM_TOKEN) | - | INACTIVE |

## 4. Базы данных

- **parkhomenko_bot.db** — SQLite. Содержит таблицы: `leads`, `content_plan`, `subscribers`.
- **database/bot.db** — Ожидаемый путь (из кода), возможно дублирует функционал или планируется.
