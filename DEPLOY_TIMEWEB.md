# Деплой бота ТЕРИОН на сервер Таймвеб

Краткая инструкция по развёртыванию на VPS/облачном сервере [Таймвеб](https://timeweb.com).

---

## Что нужно на Таймвеб

- **VPS или облачный сервер** (не тариф «Хостинг сайтов» — там нет полного доступа по SSH и фоновых процессов).  
  Подойдут: «VPS», «Облачный сервер», «Виртуальный выделенный сервер».
- Доступ по **SSH** (логин и пароль или SSH-ключ из панели Таймвеб).

---

## 1. Подключение к серверу

В панели Таймвеб найдите IP сервера и данные для SSH. Затем с вашего компьютера:

```bash
ssh root@IP_ВАШЕГО_СЕРВЕРА
```

(или другой пользователь, если создали не root)

---

## 2. Подготовка сервера (один раз)

```bash
# Обновление системы
apt update && apt upgrade -y

# Python 3.11 и git
apt install -y git python3.11 python3.11-venv python3-pip
```

---

## 3. Клонирование проекта

```bash
cd /root
# или cd /home/ваш_пользователь

git clone https://github.com/9435421-ui/parkhomenko-bot.git
cd parkhomenko-bot
```

Если папка уже есть (например, после заливки файлов), просто перейдите в неё:

```bash
cd /root/parkhomenko-bot
```

---

## 4. Виртуальное окружение и зависимости

```bash
python3.11 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

---

## 5. Настройка .env

```bash
cp .env.example .env
nano .env
```

Заполните минимум:

- `BOT_TOKEN` — токен основного бота (Антон) от @BotFather  
- `CONTENT_BOT_TOKEN` — токен бота «ДОМ ГРАНД» (если используете)  
- `YANDEX_API_KEY`, `FOLDER_ID` — для YandexGPT  
- `LEADS_GROUP_CHAT_ID` — ID рабочей группы Telegram  
- `ADMIN_ID` — ваш Telegram user_id  
- При необходимости: каналы, VK, ROUTER_AI_KEY и т.д. (см. `config.py` и `.env.example`)

Сохраните: `Ctrl+O`, Enter, выход: `Ctrl+X`.

```bash
chmod 600 .env
```

---

## 6. Проверка запуска вручную

```bash
source venv/bin/activate
python main.py
```

Убедитесь, что в логах нет ошибок. Остановка: `Ctrl+C`.

---

## 7. Автозапуск через systemd

Создайте сервис (путь и пользователь — под ваш сервер):

```bash
nano /etc/systemd/system/anton_bot.service
```

Вставьте (при необходимости замените пути и пользователя):

```ini
[Unit]
Description=TERION Bot - Telegram Bot (Антон + ДОМ ГРАНД)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/parkhomenko-bot
Environment="PATH=/root/parkhomenko-bot/venv/bin"
ExecStart=/root/parkhomenko-bot/venv/bin/python main.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal
SyslogIdentifier=anton_bot

[Install]
WantedBy=multi-user.target
```

Если используете `run_all.py` вместо `main.py`, замените в `ExecStart` на:

```text
ExecStart=/root/parkhomenko-bot/venv/bin/python run_all.py
```

Включите и запустите:

```bash
systemctl daemon-reload
systemctl enable anton_bot
systemctl start anton_bot
systemctl status anton_bot
```

Логи в реальном времени:

```bash
journalctl -u anton_bot -f
```

---

## 8. Полезные команды

| Действие        | Команда |
|-----------------|--------|
| Статус          | `systemctl status anton_bot` |
| Перезапуск      | `systemctl restart anton_bot` |
| Остановка       | `systemctl stop anton_bot` |
| Логи            | `journalctl -u anton_bot -f` |
| Обновление кода | `cd /root/parkhomenko-bot && git pull && systemctl restart anton_bot` |

---

## 9. Если на Таймвеб только «Хостинг сайтов»

На тарифах без VPS/облака нельзя держать бота 24/7: нет долгоживущих процессов и полного SSH. В этом случае нужен переход на **VPS** или **облачный сервер** в Таймвеб — тогда эта инструкция подойдёт полностью.

---

**Репозиторий:** [github.com/9435421-ui/parkhomenko-bot](https://github.com/9435421-ui/parkhomenko-bot)
