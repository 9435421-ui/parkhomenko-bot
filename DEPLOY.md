# 🚀 Инструкция по деплою бота «Лад в квартире»

Руководство по развертыванию бота на сервере для работы 24/7.

## 📋 Содержание

1. [Подготовка сервера](#подготовка-сервера)
2. [Деплой через Docker](#деплой-через-docker-рекомендуется)
3. [Деплой без Docker](#деплой-без-docker)
4. [Мониторинг и логи](#мониторинг-и-логи)
5. [Бэкапы](#бэкапы)
6. [Обновление](#обновление)

---

## 🖥️ Подготовка сервера

### Минимальные требования:
- **ОС:** Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- **RAM:** 512 MB (рекомендуется 1 GB)
- **CPU:** 1 ядро
- **Диск:** 2 GB свободного места
- **Python:** 3.11+
- **Docker:** 20.10+ (при использовании Docker)

### Подключение к серверу

**Продакшен:** `176.124.219.183`

```bash
ssh root@176.124.219.183
```

Быстрые команды (из корня проекта):
- **Деплой:** `./scripts/deploy-remote.sh deploy`
- **Проверка статуса:** `./scripts/deploy-remote.sh check`

В Cursor можно сказать: *«запусти деплой»* или *«проверь снова»* — агент выполнит соответствующие команды на этом сервере.

### Установка зависимостей:

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y git python3.11 python3.11-venv python3-pip
```

**CentOS/RHEL:**
```bash
sudo yum install -y git python3.11 python3.11-pip
```

---

## 🐳 Деплой через Docker (РЕКОМЕНДУЕТСЯ)

### 1. Установка Docker

**Ubuntu/Debian:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

**Установка Docker Compose:**
```bash
sudo apt install docker-compose-plugin
```

### 2. Клонирование репозитория

```bash
cd ~
git clone https://github.com/your-org/Lad_v_kvartire_bot.git
cd Lad_v_kvartire_bot
```

### 3. Настройка окружения

```bash
cp .env.example .env
nano .env
```

**Заполните обязательные поля:**
```env
TELEGRAM_TOKEN=ваш_токен_от_BotFather
YANDEX_API_KEY=ваш_api_key
FOLDER_ID=ваш_folder_id
LEADS_GROUP_CHAT_ID=-1003370698977
ADMIN_ID=ваш_user_id
```

### 4. Запуск бота

```bash
docker compose up -d --build
```

### 5. Проверка статуса

```bash
docker compose ps
docker compose logs -f bot
```

### 6. Управление

**Остановить:**
```bash
docker compose down
```

**Перезапустить:**
```bash
docker compose restart
```

**Обновить:**
```bash
git pull
docker compose up -d --build
```

---

## 📦 Деплой без Docker

### 1. Клонирование репозитория

```bash
cd ~
git clone https://github.com/your-org/Lad_v_kvartire_bot.git
cd Lad_v_kvartire_bot
```

### 2. Создание виртуального окружения

```bash
python3.11 -m venv venv
source venv/bin/activate
```

### 3. Установка зависимостей

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Настройка окружения

```bash
cp .env.example .env
nano .env
```

### 5. Создание systemd сервиса

```bash
sudo nano /etc/systemd/system/lad-bot.service
```

**Содержимое файла:**
```ini
[Unit]
Description=Lad v Kvartire Telegram Bot
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/Lad_v_kvartire_bot
Environment="PATH=/home/your-username/Lad_v_kvartire_bot/venv/bin"
ExecStart=/home/your-username/Lad_v_kvartire_bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Замените:**
- `your-username` на ваш логин

### 6. Запуск сервиса

```bash
sudo systemctl daemon-reload
sudo systemctl enable lad-bot
sudo systemctl start lad-bot
```

### 7. Проверка статуса

```bash
sudo systemctl status lad-bot
journalctl -u lad-bot -f
```

### 8. Управление

**Остановить:**
```bash
sudo systemctl stop lad-bot
```

**Перезапустить:**
```bash
sudo systemctl restart lad-bot
```

**Посмотреть логи:**
```bash
journalctl -u lad-bot -n 100
```

---

## 📊 Мониторинг и логи

### Просмотр логов (Docker)

```bash
# Последние 100 строк
docker compose logs --tail=100 bot

# В реальном времени
docker compose logs -f bot

# Только ошибки
docker compose logs bot | grep ERROR
```

### Просмотр логов (systemd)

```bash
# Последние 50 строк
journalctl -u lad-bot -n 50

# В реальном времени
journalctl -u lad-bot -f

# За сегодня
journalctl -u lad-bot --since today
```

### Мониторинг ресурсов

```bash
# Docker
docker stats lad_v_kvartire_bot

# Системные ресурсы
htop
```

---

## 💾 Бэкапы

### Автоматический бэкап

**Создайте cron задачу:**
```bash
crontab -e
```

**Добавьте строку (бэкап каждый день в 3:00):**
```bash
0 3 * * * cd /home/your-username/Lad_v_kvartire_bot && python backup_db.py
```

### Ручной бэкап

```bash
cd ~/Lad_v_kvartire_bot
python backup_db.py
```

### Восстановление из бэкапа

```bash
python backup_db.py restore backups/bot_db_backup_20260126_030000.db
```

### Скачать бэкап на локальный компьютер

```bash
scp user@server:/home/user/Lad_v_kvartire_bot/backups/bot_db_backup_*.db ./
```

---

## 🔄 Обновление

### Docker

```bash
cd ~/Lad_v_kvartire_bot
git pull
docker compose down
docker compose up -d --build
```

### Systemd

```bash
cd ~/Lad_v_kvartire_bot
source venv/bin/activate
git pull
pip install -r requirements.txt
sudo systemctl restart lad-bot
```

---

## 🔧 Устранение неполадок

### Бот не запускается

1. **Проверьте логи:**
   ```bash
   docker compose logs bot
   # или
   journalctl -u lad-bot -n 100
   ```

2. **Проверьте .env:**
   ```bash
   cat .env | grep TELEGRAM_TOKEN
   ```

3. **Проверьте доступность Telegram API:**
   ```bash
   curl -I https://api.telegram.org
   ```

### Бот не отвечает

1. **Проверьте статус:**
   ```bash
   docker compose ps
   # или
   sudo systemctl status lad-bot
   ```

2. **Проверьте базу данных:**
   ```bash
   ls -lh database/bot.db
   ```

3. **Перезапустите:**
   ```bash
   docker compose restart
   # или
   sudo systemctl restart lad-bot
   ```

### База данных повреждена

```bash
# Восстановите из последнего бэкапа
python backup_db.py restore backups/bot_db_backup_latest.db
```

---

## 🔐 Безопасность

### 1. Настройте firewall

```bash
sudo ufw allow 22/tcp
sudo ufw enable
```

### 2. Используйте SSH ключи

```bash
ssh-keygen -t ed25519
ssh-copy-id user@server
```

### 3. Настройте автообновления

```bash
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 4. Ограничьте права доступа к .env

```bash
chmod 600 .env
```

---

## 📱 Полезные команды

### Проверка версии Python

```bash
python3.11 --version
```

### Проверка портов

```bash
sudo netstat -tulpn | grep python
```

### Очистка логов Docker

```bash
docker system prune -a
```

### Проверка использования диска

```bash
df -h
du -sh ~/Lad_v_kvartire_bot/*
```

---

## 🆘 Поддержка

При возникновении проблем:

1. Проверьте логи
2. Убедитесь, что .env заполнен корректно
3. Проверьте доступ к Telegram API
4. Создайте issue в репозитории

---

**Версия:** 2.0  
**Дата:** 26.01.2026  
**Автор:** Cline (VS Code AI Assistant)
