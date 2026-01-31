#!/bin/bash
source venv/bin/activate
while true; do
    python3 content_bot_mvp/main.py >> bot.log 2>&1
    echo "$(date): Бот упал, перезапуск через 5 секунд..." >> bot.log
    sleep 5
done
