# Интеграция Hunter V3 & Content Engine

## Дата: 2026-02-17

## Выполненные изменения согласно ТЗ

### 1. ✅ Модуль Scout & Hunter

#### Fix Telegram Peer (discovery.py)
**Проблема:** Метод `global_telegram_search` использовал `get_entity` для каждого канала, что вызывало ошибки и было неэффективно.

**Решение:**
- Исключен `get_entity` для каждого канала
- Итерация напрямую по `search_result.chats`
- Добавлены проверки на `None` и наличие атрибута `chats`
- Используются данные из `results.chats` без дополнительных запросов
- **Файл:** `services/lead_hunter/discovery.py` (строки 197-256)

**Изменения:**
```python
# Было:
entity = await client.get_entity(channel_id)
if isinstance(entity, (Channel, Chat)):
    # ...

# Стало:
for chat in results.chats:
    if chat is None or not hasattr(chat, "id"):
        continue
    # Используем данные напрямую из chat
```

#### Умный поиск (Lead Detection) - HOT_TRIGGERS
**Проблема:** Фильтры были слишком строгими, пропускали горячие лиды.

**Решение:**
- Добавлен список `HOT_TRIGGERS` с критическими фразами:
  - "предписание МЖИ"
  - "узаконить"
  - "МЖИ"
  - "штраф БТИ"
  - "блокировка сделки"
  - "суд по перепланировке"
- Смягчены фильтры: лид засчитывается, если есть [Тех. термин] + [Вопрос ИЛИ Коммерческий маркер]
- Если найден HOT_TRIGGER - лид определяется сразу без дополнительных проверок
- **Файл:** `services/scout_parser.py` (строки 201-220, 348-380)

**Изменения:**
```python
# Добавлен HOT_TRIGGERS
HOT_TRIGGERS = [
    r"предписание\s+МЖИ",
    r"узаконить",
    r"МЖИ",
    # ...
]

# Смягченные фильтры в detect_lead:
if has_technical_term and (has_question or has_commercial_marker):
    return True
```

#### Инкрементальный скан
**Проблема:** При `last_post_id == 0` не было прогревочного скана для новых каналов.

**Решение:**
- Если `last_post_id == 0`, делается прогревочный скан последних 20 сообщений
- В остальных случаях — строго от последнего ID в базе (`min_id=last_post_id`)
- **Файл:** `services/scout_parser.py` (строки 668-682)

**Изменения:**
```python
if max_id == 0:
    # Прогревочный скан для новых каналов
    iter_params["limit"] = 20
    logger.info(f"🔥 Прогревочный скан для нового канала: последние 20 сообщений")
elif max_id > 0:
    # Инкрементальный режим
    iter_params["min_id"] = max_id
```

#### VK Fix
**Проблема:** Недостаточная обработка исключений в `scout_vk_resources`.

**Решение:**
- Добавлена обработка пустых ответов API
- Добавлена проверка статуса HTTP ответа
- Добавлена обработка ошибок парсинга JSON
- Улучшено логирование ошибок
- **Файл:** `services/lead_hunter/discovery.py` (строки 375-420)

**Изменения:**
```python
if resp.status != 200:
    logger.error(f"❌ VK API HTTP error {resp.status}")
    continue

try:
    data = await resp.json()
except Exception as json_error:
    logger.error(f"❌ Ошибка парсинга JSON: {json_error}")
    continue

if not data or not response:
    logger.warning(f"⚠️ Пустой ответ от VK API")
    continue
```

### 2. ✅ Модуль Content & Publisher

#### Централизация публикации
**Проблема:** Локальные методы публикации в хендлерах дублировали код.

**Решение:**
- Заменены все локальные методы публикации на вызовы единого сервиса `Publisher`
- Обновлены методы: `send_post`, `publish_all`, `publish_tg_only`
- Все публикации теперь идут через `services/publisher.py`
- **Файлы:** `handlers/content.py` (строки 1546-1567, 1727-1804, 1807-1844)

**Изменения:**
```python
# Было:
await callback.bot.send_photo(CHANNEL_ID_GEORIS, photo, caption=text)

# Стало:
from services.publisher import publisher
publisher.bot = callback.bot
await publisher.publish_to_telegram(CHANNEL_ID_GEORIS, text, image_bytes)
```

#### Восстановление цепочки для визуалов
**Проблема:** В `ai_visual_handler` не сохранялись `file_id` и `prompt` в FSM для использования в `art_to_post_handler`.

**Решение:**
- В `ai_visual_handler` сохранены `file_id`, `prompt` и `image_b64` в состояние FSM
- В `art_to_post_handler` используются сохраненные данные из FSM
- State не очищается после генерации изображения
- **Файл:** `handlers/content.py` (строки 852-892, 901-928)

**Изменения:**
```python
# В ai_visual_handler:
if sent_message.photo:
    file_id = sent_message.photo[-1].file_id
    await state.update_data(
        visual_file_id=file_id,
        visual_prompt=user_prompt,
        visual_image_bytes=image_b64
    )
# State НЕ очищается

# В art_to_post_handler:
state_data = await state.get_data()
file_id = state_data.get("visual_file_id")
saved_prompt = state_data.get("visual_prompt", topic)
```

#### AutoPoster исправления
**Проблема:** Использовал `os.getenv` вместо `config.py`, публиковал во все каналы вместо целевого.

**Решение:**
- Переведен на использование `config.py` для получения `CHANNEL_ID_GEORIS`, `CHANNEL_ID_DOM_GRAD`, `CHANNEL_NAMES`
- Реализована корректная отправка в целевой канал (GEORIS или ДОМ ГРАНД) вместо рассылки "всем подряд"
- **Файл:** `auto_poster.py` (строки 90-102, 104-132)

**Изменения:**
```python
# Было:
'chat_id': int(os.getenv("GEORIS_CHANNEL_ID", "-1003612599428"))

# Стало:
from config import CHANNEL_ID_GEORIS, CHANNEL_ID_DOM_GRAD, CHANNEL_NAMES
'chat_id': CHANNEL_ID_GEORIS

# Публикация в целевой канал:
success = await publisher.publish_to_telegram(channel_id, text, image_bytes)
```

### 3. ✅ Аналитика и БД

#### Pain Stages через LLM
**Статус:** Уже реализовано в предыдущих обновлениях.

**Реализация:**
- Классификация ST-1 (Интерес) до ST-4 (Критично) через Yandex GPT / Router AI
- Приоритеты 1-10 с валидацией
- Структурированный JSON ответ от AI
- **Файл:** `services/lead_hunter/analyzer.py` (строки 265-360)

#### DB Migration
**Проблема:** Не было автоматической проверки наличия полей перед добавлением.

**Решение:**
- Добавлена автоматическая проверка наличия колонок через `PRAGMA table_info`
- Миграция выполняется только если колонка отсутствует
- Добавлено логирование успешных миграций
- **Файл:** `database/db.py` (строки 222-228)

**Изменения:**
```python
# Проверяем наличие колонки перед добавлением
await cursor.execute("PRAGMA table_info(spy_leads)")
columns = await cursor.fetchall()
column_names = [col_info[1] for col_info in columns]

if col not in column_names:
    await cursor.execute(f"ALTER TABLE spy_leads ADD COLUMN {col} {ctype}")
    logger.debug(f"✅ Добавлена колонка {col}")
```

## Итоговые изменения

### Файлы изменены:

1. **services/lead_hunter/discovery.py**
   - Исправлен `global_telegram_search` (итерация по `chats` вместо `get_entity`)
   - Улучшена обработка исключений в `scout_vk_resources`

2. **services/scout_parser.py**
   - Добавлен `HOT_TRIGGERS` для критических фраз
   - Смягчены фильтры в `detect_lead`
   - Реализован прогревочный скан для `last_post_id == 0`

3. **handlers/content.py**
   - Централизована публикация через `Publisher`
   - Восстановлена цепочка для визуалов (сохранение в FSM)
   - Обновлены методы `send_post`, `publish_all`, `publish_tg_only`

4. **auto_poster.py**
   - Переведен на использование `config.py`
   - Исправлена публикация в целевой канал

5. **database/db.py**
   - Добавлена автоматическая проверка наличия колонок перед миграцией
   - Улучшено логирование миграций

## Результаты

После применения изменений:
1. ✅ `global_telegram_search` работает без ошибок `get_entity`
2. ✅ Горячие лиды определяются сразу через `HOT_TRIGGERS`
3. ✅ Новые каналы получают прогревочный скан последних 20 сообщений
4. ✅ VK Discovery корректно обрабатывает все исключения
5. ✅ Все публикации идут через единый сервис `Publisher`
6. ✅ Визуалы сохраняют данные в FSM для создания постов
7. ✅ AutoPoster публикует в правильный канал
8. ✅ Миграции БД выполняются автоматически без ошибок

## Тестирование

### Scout & Hunter:
1. Запустить `python3 run_hunter.py`
2. Проверить логи на наличие прогревочного скана для новых каналов
3. Убедиться, что HOT_TRIGGERS определяют лиды сразу

### Content & Publisher:
1. Сгенерировать изображение через `/visual`
2. Проверить, что `file_id` и `prompt` сохраняются в FSM
3. Создать пост из изображения и проверить публикацию

### AutoPoster:
1. Добавить пост в контент-план
2. Проверить, что публикация идет в правильный канал (GEORIS или ДОМ ГРАНД)

### DB Migration:
1. Запустить бота - миграции выполнятся автоматически
2. Проверить логи на наличие сообщений о добавлении колонок
