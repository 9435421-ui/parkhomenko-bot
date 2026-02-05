#!/bin/bash
# run_main_bot.sh - Запуск основного бота с авто-рестартом
PID_FILE="main_bot.pid"

# Убиваем предыдущие процессы основного бота
pgrep -af "python3.*main.py" | grep -v "content_bot_mvp" | awk '{print $1}' | xargs kill 2>/dev/null || true

if [ -f "$PID_FILE" ]; then
    kill $(cat "$PID_FILE") 2>/dev/null
    rm "$PID_FILE"
fi

source venv/bin/activate

# Записываем PID текущего шелл-скрипта
echo $$ > "$PID_FILE"

while true; do
    echo "$(date): Запуск основного бота..." >> main_bot.log
    python3 -u main.py >> main_bot.log 2>> main_bot_error.log
    echo "$(date): Основной бот упал, перезапуск через 5 секунд..." >> main_bot.log
    sleep 5
done
