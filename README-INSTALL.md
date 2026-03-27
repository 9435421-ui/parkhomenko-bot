# 📦 Установка GEORIS Content Bot

## 📁 Структура проекта

```
parkhomenko-bot/
├── main.py                 # Точка входа
├── config.py              # Конфигурация ✅ ОБНОВЛЁН
├── requirements.txt       # Зависимости
├── .env                   # Переменные окружения
├── handlers/
│   ├── __init__.py
│   ├── content.py         # ✅ МОЙ КОД (500+ строк)
│   ├── vk_publisher.py    # ✅ МОЙ КОД (VK с кнопками)
│   ├── max_uploader.py    # ✅ МОЙ КОД (заглушка MAX.ru)
│   └── admin.py           # Ваш существующий
├── services/              # Сервисы
├── database/              # База данных
└── utils/                 # Утилиты
```

---

## 🚀 Быстрый старт

### 1. Установка файлов

```bash
cd ~/PARKHOMENKO_BOT

# Сохранить старые файлы
mv handlers/content.py handlers/content.py.old.$(date +%s)
mv handlers/vk_publisher.py handlers/vk_publisher.py.old.$(date +%s) 2>/dev/null || true

# Создать новые файлы
nano handlers/content.py      # Вставить полный код content.py
nano handlers/vk_publisher.py # Вставить код vk_publisher.py
nano handlers/max_uploader.py # Вставить код max_uploader.py
```

### 2. Обновить config.py

```bash
nano config.py
# Добавить в конец:
```

```python
# === CONTENT BOT (GEORIS) ===
# Альтернативные названия каналов (для совместимости)
GEORIS_CHANNEL_ID = CHANNEL_ID_GEORIS
DOM_GRAND_CHANNEL_ID = CHANNEL_ID_DOM_GRAD

# MAX.ru (ready-to-enable)
MAX_API_KEY = os.getenv("MAX_API_KEY", "")
MAX_ENABLED = os.getenv("MAX_ENABLED", "false").lower() == "true"

# RouterAI URL
ROUTER_AI_URL = os.getenv("ROUTER_AI_URL", "https://routerai.ru/api/v1")

# Яндекс АРТ
YANDEX_ART_ENABLED = os.getenv("YANDEX_ART_ENABLED", "true").lower() == "true"
```

### 3. Обновить .env

```bash
nano .env
```

```env
# Content Bot (GEORIS/DOM GRAND)
CONTENT_BOT_TOKEN=your_content_bot_token_here

# VK
VK_TOKEN=your_vk_token_here
VK_GROUP_ID=235569022

# Yandex ART
YANDEX_API_KEY=your_yandex_api_key
FOLDER_ID=your_folder_id

# RouterAI
ROUTER_AI_KEY=your_router_ai_key

# MAX.ru (опционально)
MAX_API_KEY=b5766865e14b364805c35984fd158b5e5fd5caa1b450728f252c0787aa129460
MAX_ENABLED=false

# Квиз ссылка
VK_QUIZ_LINK=https://t.me/GEORIS_KvizBot?start=quiz
```

### 4. Установка зависимостей

```bash
# Создать виртуальное окружение
python3 -m venv venv

# Активировать
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# Установить зависимости
pip install aiogram aiohttp Pillow python-dotenv apscheduler

# Проверить
pip list | grep aiogram
```

### 5. Запуск

```bash
# Ручной запуск
python main.py

# С логами в файл
python main.py 2>&1 | tee bot.log
```

---

## 🔧 Systemd сервис (автозапуск)

**Файл:** `/etc/systemd/system/georis-bot.service`

```ini
[Unit]
Description=GEORIS Content Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/PARKHOMENKO_BOT
Environment=PYTHONUNBUFFERED=1
ExecStart=/root/PARKHOMENKO_BOT/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Команды:**

```bash
# Создать сервис
sudo nano /etc/systemd/system/georis-bot.service

# Активировать
sudo systemctl daemon-reload
sudo systemctl enable georis-bot
sudo systemctl start georis-bot

# Проверить статус
sudo systemctl status georis-bot

# Логи
sudo journalctl -u georis-bot -f
```

---

## ✅ Проверка работы

1. Отправить `/start` боту **@GEORIS_Content_Bot**
2. Должно появиться меню:
   - 📸 Фото → Описание → Пост
   - 🎨 ИИ-Визуал
   - 📅 7 дней прогрева
   - 📰 Новость
   - 📋 Интерактивный План
   - 📝 Быстрый текст

---

## 📝 Функции бота

| Кнопка | Описание |
|--------|----------|
| 📸 Фото → Описание → Пост | Загрузка фото → AI описание → публикация |
| 🎨 ИИ-Визуал | Генерация изображений (Яндекс АРТ / Gemini) |
| 📅 7 дней прогрева | Серия постов на заданную тему |
| 📰 Новость | Экспертная новость |
| 📋 Интерактивный План | Контент-план на N дней |
| 📝 Быстрый текст | Быстрая генерация текста |

### Кнопки публикации

- 🚀 **Опубликовать везде** — TG (GEORIS + ДОМ ГРАНД) + VK
- 📱 **Только TG** — только Telegram каналы
- 🌐 **Только VK** — только ВКонтакте
- 🗑 **В черновики** — сохранить в топик 85
- ✏️ **Редактировать** — изменить текст
- ❌ **Отмена** — отменить

---

## 📋 Требования

```
aiogram>=3.0.0
aiohttp>=3.8.0
Pillow>=9.0.0
python-dotenv>=0.19.0
apscheduler>=3.9.0
```

---

## ⚠️ Важно

- MAX.ru отключен (`enabled = False`)
- После тестирования TG+VK можно включить MAX
- Все посты сохраняются в БД (`content_posts`)
- Для фонового запуска используйте `screen` или `systemd`

### Screen (альтернатива systemd)

```bash
# Создать сессию
screen -S georis-bot
python main.py
# Ctrl+A, D — отключиться

# Подключиться обратно
screen -r georis-bot
```
