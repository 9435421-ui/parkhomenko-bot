# 🔍 Экспертный анализ архитектуры GEORIS и план миграции на "Жюль"

**Дата:** 17 февраля 2026  
**Проект:** GEORIS Bot (parkhomenko-bot)  
**Задача:** Сравнение текущей архитектуры с новой архитектурой "Жюль" и оценка целесообразности миграции

---

## 📊 Текущая архитектура GEORIS (детальный анализ)

### 1. Структура проекта

```
parkhomenko-bot/
├── main.py                    # Точка входа: 2 бота (АНТОН + ДОМ ГРАНД)
├── config.py                  # Конфигурация (токены, каналы, топики)
├── database/
│   ├── db.py                  # Основная БД (SQLite + aiosqlite)
│   └── __init__.py
├── handlers/                  # Обработчики событий Telegram
│   ├── start.py               # Онбординг, главное меню
│   ├── quiz.py                # Квиз (FSM, сбор заявки)
│   ├── dialog.py              # Диалог с RAG
│   ├── admin.py               # Админка, управление лидами
│   ├── content.py             # Контент-меню, публикация
│   ├── invest.py              # Инвест-калькулятор
│   ├── sales_agent.py         # Продажный агент (5-шаговый скрипт)
│   └── vk_publisher.py        # Публикация в VK
├── services/
│   ├── lead_hunter/           # Система поиска лидов
│   │   ├── hunter.py          # Основной класс LeadHunter
│   │   ├── analyzer.py         # Анализ постов (ST-1...ST-4)
│   │   ├── discovery.py       # Поиск новых источников
│   │   └── outreach.py        # Исходящие сообщения
│   ├── scout_parser.py        # Парсинг TG/VK каналов
│   ├── competitor_spy.py      # Мониторинг конкурентов
│   ├── geospy.py              # Гео-шпион (чаты ЖК)
│   ├── publisher.py           # Публикация контента
│   ├── image_generator.py     # Генерация изображений
│   └── sales_reminders.py     # Напоминания продажам
├── hunter_standalone/          # Автономный анализ лидов
│   ├── hunter.py              # Standalone LeadHunter
│   └── database.py            # HunterDatabase (potential_leads.db)
├── utils/
│   ├── yandex_gpt.py          # YandexGPT API
│   ├── yandex_ai_agents.py    # Yandex AI Agent API (Шпион, Антон)
│   ├── router_ai.py           # Router AI (fallback)
│   ├── knowledge_base.py      # RAG система
│   ├── bot_config.py          # Конфигурация ботов
│   ├── yandex_vision.py       # Yandex Vision API
│   └── image_compressor.py    # Сжатие изображений
├── knowledge_base/            # База знаний (80+ документов)
│   ├── 01_Федеральные_законы/
│   ├── 02_Кодексы_и_ответственность/
│   ├── 03_Своды_правил_и_СП/
│   ├── 04_Москва/
│   ├── 05_Московская_область/
│   ├── 06_Процедуры_и_документы/
│   ├── 07_объекты_культурного_наследия_ОКН/
│   └── 09_ИИ_консультант/
└── scripts/
    ├── init_database.py       # Инициализация БД
    └── init_spy_targets.py    # Загрузка целей для шпиона
```

### 2. База данных (SQLite)

#### Основные таблицы:

**users** — пользователи бота
- `user_id` (PRIMARY KEY)
- `username`, `first_name`, `last_name`, `phone`
- `created_at`, `last_interaction`

**user_states** — состояния пользователей (FSM)
- `user_id` (PRIMARY KEY, FK → users)
- `mode` (dialog/quiz/admin)
- `quiz_step` (0-10)
- `name`, `phone`, `extra_contact`
- `object_type`, `city`, `floor`, `total_floors`
- `remodeling_status`, `change_plan`, `bti_status`
- `consent_given`, `contact_received`
- `updated_at`

**dialog_history** — история диалогов
- `id` (PRIMARY KEY)
- `user_id` (FK → users)
- `role` (user/assistant)
- `message` (TEXT)
- `created_at`

**leads** — лиды от квиза
- `id` (PRIMARY KEY)
- `user_id` (FK → users)
- `name`, `phone`, `extra_contact`
- `object_type`, `city`, `floor`, `total_floors`, `area`
- `remodeling_status`, `change_plan`, `bti_status`
- `extra_questions`
- `created_at`
- `sent_to_group` (BOOLEAN)
- `thread_id` (INTEGER)

**spy_leads** — лиды от шпиона (TG/VK)
- `id` (PRIMARY KEY)
- `source_type` (telegram/vk)
- `source_name` (TEXT)
- `author_id`, `username`, `profile_url`
- `text` (TEXT)
- `url` (TEXT)
- `pain_stage` (ST-1/ST-2/ST-3/ST-4)
- `priority_score` (1-10)
- `created_at`
- `contacted_at` (TIMESTAMP)
- `sent_to_hot_leads` (BOOLEAN)

**target_resources** — целевые ресурсы для мониторинга
- `id` (PRIMARY KEY)
- `type` (telegram/vk)
- `link` (UNIQUE)
- `title`
- `is_active` (BOOLEAN)
- `last_post_id` (INTEGER)
- `created_at`, `updated_at`
- `notes` (TEXT)

**content_plan** — контент-план постов
- `id` (PRIMARY KEY)
- `type` (TEXT)
- `channel` (georis/dom_grand)
- `title`, `body`, `cta`
- `theme`
- `publish_date` (TIMESTAMP)
- `status` (draft/approved/published)
- `image_url`, `image_prompt`
- `admin_id`
- `published_at`, `created_at`

**sales_conversations** — продажные диалоги
- `id` (PRIMARY KEY)
- `user_id` (FK → users)
- `lead_id` (FK → spy_leads)
- `step` (1-5)
- `data` (JSON)
- `created_at`, `updated_at`

**clients_birthdays** — дни рождения клиентов
- `id` (PRIMARY KEY)
- `user_id` (FK → users)
- `name`
- `birth_date` (DATE)
- `channel` (telegram/vk)
- `greeting_sent` (BOOLEAN)
- `created_at`, `updated_at`

**content_history** — история контента (финансовый трекинг)
- `id` (PRIMARY KEY)
- `post_text`, `image_url`
- `model_used` (VARCHAR)
- `cost_rub` (DECIMAL)
- `platform`, `channel`
- `post_id`
- `created_at`
- `is_archived` (BOOLEAN)

### 3. Ключевые компоненты

#### 3.1. Система поиска лидов (Lead Hunter v3.1)

**Архитектура:**
- `ScoutParser` — парсинг TG/VK каналов
- `LeadAnalyzer` — анализ постов (ST-1...ST-4, priority_score 1-10)
- `Discovery` — поиск новых источников
- `Outreach` — исходящие сообщения
- `HunterDatabase` — автономная БД потенциальных лидов

**Особенности:**
- Парсинг каждые 20 минут через `run_hunter.py`
- Инкрементальный парсинг через `last_post_id`
- Фильтрация стоп-слов до отправки в AI
- Классификация по стадиям боли (ST-1...ST-4)
- Приоритизация (priority_score 1-10)
- Автоматическая отправка карточек в рабочую группу
- Тихие уведомления для низкоприоритетных лидов

#### 3.2. Квиз (FSM)

**Этапы:**
1. Согласие на обработку ПД
2. Получение контакта
3. Город
4. Тип объекта (квартира/коммерция/дом)
5. Этажность
6. Площадь
7. Статус перепланировки
8. Описание изменений
9. План (фото)
10. Доп. вопросы

**Особенности:**
- Поддержка голосовых сообщений (транскрибация через Yandex SpeechKit)
- Сохранение "тёплых" лидов при брошенном квизе
- Предварительное заключение от Агента-Антона после завершения
- Уведомление эксперту в рабочую группу

#### 3.3. Диалог с RAG

**Архитектура:**
- Поиск в базе знаний (80+ документов)
- Учет истории диалога (10 последних сообщений)
- Генерация ответов через Router AI (Kimi/Qwen)
- Fallback на YandexGPT для персональных данных

**Особенности:**
- Автоматический переход к квизу при триггер-словах
- Короткие ответы без повторов
- Учет контекста разговора

#### 3.4. Контент-меню

**Функции:**
- Быстрый текст
- 7 дней прогрева
- Интерактивный план
- Новость
- Интересный факт
- Праздник РФ
- Фото → Описание → Пост
- Темы от Шпиона

**Публикация:**
- Telegram (ГЕОРИС, ДОМ ГРАНД)
- VK
- MAX.ru

#### 3.5. Продажный агент (5-шаговый скрипт)

**Этапы:**
1. Приветствие + Квалификация
2. Продажа ценности
3. Захват документа
4. Презентация УТП
5. Переход к квизу

**Особенности:**
- State-Machine (StatesGroup)
- Автоматические напоминания (24ч и 3 дня)
- Шаблоны ответов по стадиям боли

### 4. Технологический стек

- **Фреймворк:** Aiogram 3.x
- **БД:** SQLite + aiosqlite
- **AI:** YandexGPT, Yandex AI Agents, Router AI
- **Планировщик:** APScheduler
- **Парсинг:** Telethon (Telegram), vk_api (VK)
- **RAG:** Векторный поиск в базе знаний

### 5. Интеграции

1. **Telegram Bot API** — два бота (АНТОН + ДОМ ГРАНД)
2. **VK API** — публикация и парсинг
3. **Yandex Cloud** — GPT, AI Agents, Vision, SpeechKit
4. **Router AI** — fallback для AI
5. **MAX.ru** — публикация контента

---

## 🎯 Критерии оценки архитектуры "Жюль"

Для принятия решения о миграции необходимо сравнить:

### 1. Структура базы данных
- ✅ Соответствие схеме GEORIS
- ✅ Поддержка всех текущих таблиц
- ✅ Миграции данных
- ✅ Производительность (WAL режим, индексы)

### 2. Архитектура кода
- ✅ Разделение ответственности (handlers/services/utils)
- ✅ Масштабируемость
- ✅ Тестируемость
- ✅ Поддержка двухботовой архитектуры

### 3. Функциональность
- ✅ Квиз (FSM, все этапы)
- ✅ Диалог с RAG
- ✅ Lead Hunter (парсинг, анализ, карточки)
- ✅ Контент-меню
- ✅ Продажный агент
- ✅ Планировщик задач

### 4. Интеграции
- ✅ Telegram Bot API
- ✅ VK API
- ✅ Yandex Cloud
- ✅ Router AI

### 5. Производительность и надежность
- ✅ WAL режим БД
- ✅ Lock-файл (предотвращение дублирования)
- ✅ Обработка ошибок
- ✅ Логирование

---

## 📋 План действий для анализа "Жюль"

### Шаг 1: Распаковка и изучение структуры
1. Распаковать архив "Жюль.zip"
2. Изучить структуру проекта
3. Проанализировать схему БД
4. Изучить основные классы и модули

### Шаг 2: Сравнительный анализ
1. Сравнить структуру БД
2. Сравнить архитектуру кода
3. Сравнить функциональность
4. Выявить различия и улучшения

### Шаг 3: Оценка целесообразности миграции
1. Оценить преимущества новой архитектуры
2. Оценить риски миграции
3. Оценить трудозатраты
4. Принять решение

### Шаг 4: План миграции (если решение положительное)
1. Составить список компонентов для переноса
2. Определить порядок миграции
3. Подготовить скрипты миграции данных
4. Составить план тестирования

---

## ⚠️ Важные замечания

1. **Архив "Жюль.zip" не найден** в текущей директории проекта
2. Для полного анализа необходимо предоставить архив или описать структуру "Жюль"
3. Текущая архитектура GEORIS является зрелой и функциональной
4. Миграция должна быть обоснована конкретными преимуществами

---

## 🔄 Следующие шаги

1. **Предоставить архив "Жюль.zip"** или описать его структуру
2. **Провести детальный анализ** архитектуры "Жюль"
3. **Сравнить** с текущей архитектурой GEORIS
4. **Принять решение** о целесообразности миграции
5. **Составить план миграции** (если решение положительное)

---

**Статус:** Ожидание архива "Жюль.zip" для анализа
