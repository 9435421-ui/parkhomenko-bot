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

Полный список файлов зафиксирован в `report_files.txt`.

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
