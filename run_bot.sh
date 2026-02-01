#!/bin/bash
# run_bot.sh - Запуск бота с авто-рестартом
PID_FILE="content_bot_mvp/bot.pid"

# Убиваем предыдущий процесс, если он есть
if [ -f "$PID_FILE" ]; then
    kill $(cat "$PID_FILE") 2>/dev/null
    rm "$PID_FILE"
fi

source venv/bin/activate

# Записываем PID текущего шелл-скрипта
echo $$ > "$PID_FILE"

while true; do
    echo "$(date): Запуск бота..." >> bot.log
    # Переходим в директорию бота для корректной загрузки .env и файлов
    cd content_bot_mvp
    python3 -u main.py >> ../bot.log 2>&1
    cd ..
    echo "$(date): Бот упал, перезапуск через 5 секунд..." >> bot.log
    sleep 5
done
