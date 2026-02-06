# 🚀 Быстрый запуск на сервере

Пошаговые команды для загрузки и запуска бота на сервере.

---

## 📦 ШАГ 1: Подготовка локального компьютера

### Загрузите проект на GitHub (если ещё не сделали)

```bash
# На вашем компьютере (в папке проекта)
cd c:\Lad_v_kvartire_bot

# Инициализация Git (если не сделано)
git init
git add .
git commit -m "Initial commit - Lad v Kvartire bot"

# Создайте репозиторий на GitHub и загрузите
git remote add origin https://github.com/YOUR_USERNAME/Lad_v_kvartire_bot.git
git branch -M main
git push -u origin main
```

**Альтернатива: Загрузка через SCP (без Git)**

```bash
# На вашем компьютере
scp -r c:\Lad_v_kvartire_bot user@your-server-ip:/home/user/
```

---

## 🖥️ ШАГ 2: Подключение к серверу

```bash
ssh user@your-server-ip
```

**Замените:**
- `user` на ваш логин на сервере
- `your-server-ip` на IP адрес сервера

---

## 🐳 ШАГ 3: Установка Docker (ВАРИАНТ 1 - Рекомендуется)

### 3.1. Установка Docker

```bash
# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER

# Перезайдите в SSH для применения изменений
exit
ssh user@your-server-ip
```

### 3.2. Установка Docker Compose

```bash
# Установка Docker Compose
sudo apt update
sudo apt install -y docker-compose-plugin

# Проверка установки
docker --version
docker compose version
```

### 3.3. Клонирование проекта

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/Lad_v_kvartire_bot.git
cd Lad_v_kvartire_bot
```

### 3.4. Настройка .env

```bash
# Создание .env из шаблона
cp .env.example .env

# Редактирование .env
nano .env
```

**В nano редакторе заполните (минимум):**
```env
TELEGRAM_TOKEN=7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw  # ваш токен
YANDEX_API_KEY=AQVNxxxxxxxxxxxxxxxxxxxxxxxxxxxx              # ваш API ключ
FOLDER_ID=b1gxxxxxxxxxxxxxxxxxxxx                            # ваш folder ID
LEADS_GROUP_CHAT_ID=-1003370698977
ADMIN_ID=123456789                                            # ваш Telegram ID
```

**Сохранить:** `Ctrl+O`, `Enter`, `Ctrl+X`

### 3.5. Запуск бота

```bash
# Запуск
docker compose up -d --build

# Проверка статуса
docker compose ps

# Просмотр логов
docker compose logs -f bot
```

**Готово! Бот работает 24/7** ✅

**Полезные команды:**
```bash
# Остановить бота
docker compose down

# Перезапустить бота
docker compose restart

# Обновить бота
git pull
docker compose up -d --build

# Бэкап базы данных
python backup_db.py
```

---

## 🐍 ШАГ 3: Без Docker (ВАРИАНТ 2 - Альтернатива)

### 3.1. Установка Python

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip git
```

### 3.2. Клонирование проекта

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/Lad_v_kvartire_bot.git
cd Lad_v_kvartire_bot
```

### 3.3. Настройка .env

```bash
cp .env.example .env
nano .env
```

**Заполните как в варианте с Docker**

### 3.4. Создание systemd сервиса

```bash
# Узнайте ваш логин
whoami

# Создайте сервис (замените YOUR_USERNAME на ваш логин)
sudo nano /etc/systemd/system/lad-bot.service
```

**Вставьте в файл:**
```ini
[Unit]
Description=Lad v Kvartire Telegram Bot
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/Lad_v_kvartire_bot
Environment="PATH=/home/YOUR_USERNAME/Lad_v_kvartire_bot/venv/bin"
ExecStart=/home/YOUR_USERNAME/Lad_v_kvartire_bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Замените YOUR_USERNAME на ваш логин (результат команды `whoami`)**

**Сохранить:** `Ctrl+O`, `Enter`, `Ctrl+X`

### 3.5. Установка зависимостей и запуск

```bash
# Создание виртуального окружения
python3.11 -m venv venv

# Активация
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Включение и запуск сервиса
sudo systemctl daemon-reload
sudo systemctl enable lad-bot
sudo systemctl start lad-bot

# Проверка статуса
sudo systemctl status lad-bot

# Просмотр логов
journalctl -u lad-bot -f
```

**Готово! Бот работает 24/7** ✅

**Полезные команды:**
```bash
# Остановить бота
sudo systemctl stop lad-bot

# Перезапустить бота
sudo systemctl restart lad-bot

# Обновить бота
cd ~/Lad_v_kvartire_bot
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart lad-bot

# Бэкап базы данных
cd ~/Lad_v_kvartire_bot
python backup_db.py
```

---

## 📊 Проверка работы бота

### 1. Откройте Telegram
### 2. Найдите вашего бота (@your_bot_name)
### 3. Отправьте `/start`

**Должно появиться:**
```
👋 Здравствуйте! Я Антон, ИИ-помощник эксперта
Пархоменко Юлии Владимировны по согласованию перепланировок.
```

**Если работает - всё готово!** ✅

---

## 🔧 Устранение проблем

### Бот не отвечает

**Docker:**
```bash
docker compose logs bot
docker compose restart
```

**Systemd:**
```bash
journalctl -u lad-bot -n 50
sudo systemctl restart lad-bot
```

### Проверка .env

```bash
cat .env | grep TELEGRAM_TOKEN
```

### Проверка доступности Telegram

```bash
curl -I https://api.telegram.org
```

---

## 💾 Автоматический бэкап

```bash
# Откройте crontab
crontab -e

# Добавьте строку (бэкап каждый день в 3:00)
# Замените YOUR_USERNAME на ваш логин
0 3 * * * cd /home/YOUR_USERNAME/Lad_v_kvartire_bot && python backup_db.py
```

---

## 📱 Получение токенов

### Telegram Bot Token

1. Откройте [@BotFather](https://t.me/BotFather)
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Скопируйте токен в .env

### Yandex API Key

1. [Перейдите в Yandex Cloud](https://cloud.yandex.ru/)
2. Создайте аккаунт/войдите
3. Создайте каталог
4. Получите API ключ
5. Скопируйте в .env

### Ваш Telegram ID

1. Откройте [@userinfobot](https://t.me/userinfobot)
2. Отправьте `/start`
3. Скопируйте ваш ID в .env

---

## ✅ Чеклист готовности

- [ ] Сервер настроен (SSH доступ)
- [ ] Docker установлен ИЛИ Python 3.11 установлен
- [ ] Проект загружен на сервер
- [ ] .env создан и заполнен
- [ ] Бот запущен
- [ ] Бот отвечает в Telegram
- [ ] Cron бэкапы настроены

---

**Всё готово! Бот работает 24/7!** 🎉
