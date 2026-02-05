#!/bin/bash
# full_check_bot_report.sh - Безопасная проверка content_bot_mvp

REPORT_FILE="content_bot_mvp/bot_full_report.txt"
echo "=== Полная проверка контент-бота ТЕРИОН ===" > "$REPORT_FILE"
echo "Дата проверки: $(date)" >> "$REPORT_FILE"

echo -e "\n=== 1. Структура проекта ===" >> "$REPORT_FILE"
find content_bot_mvp -maxdepth 2 -not -path '*/.*' >> "$REPORT_FILE"

echo -e "\n=== 2. Виртуальное окружение ===" >> "$REPORT_FILE"
if [ -d "venv" ]; then
    echo "✅ venv существует" >> "$REPORT_FILE"
    source venv/bin/activate
    pip list | grep -E "pyTelegramBotAPI|openai|schedule|python-dotenv" >> "$REPORT_FILE"
else
    echo "❌ venv не найден" >> "$REPORT_FILE"
fi

echo -e "\n=== 3. Проверка .env (наличие переменных) ===" >> "$REPORT_FILE"
if [ -f "content_bot_mvp/.env" ]; then
    for var in BOT_TOKEN OPENAI_API_KEY CHANNEL_ID LEADS_GROUP_CHAT_ID; do
        if grep -q "^$var=" content_bot_mvp/.env; then
            echo "✅ $var установлена" >> "$REPORT_FILE"
        else
            echo "❌ $var ОТСУТСТВУЕТ" >> "$REPORT_FILE"
        fi
    done
else
    echo "❌ Файл .env не найден" >> "$REPORT_FILE"
fi

echo -e "\n=== 4. Статус процесса ===" >> "$REPORT_FILE"
if pgrep -f "content_bot_mvp/main.py" > /dev/null; then
    echo "✅ Бот запущен (PID: $(pgrep -f "content_bot_mvp/main.py"))" >> "$REPORT_FILE"
else
    echo "❌ Бот НЕ запущен" >> "$REPORT_FILE"
fi

echo -e "\n=== 5. Последние логи (без токенов) ===" >> "$REPORT_FILE"
if [ -f "bot.log" ]; then
    tail -n 10 bot.log | sed 's/[0-9]\{9,10\}:[a-zA-Z0-9_-]\{35\}/[TOKEN_HIDDEN]/g' >> "$REPORT_FILE"
else
    echo "Лог-файл не найден" >> "$REPORT_FILE"
fi

echo -e "\n=== 6. Завершено ===" >> "$REPORT_FILE"
echo "Отчёт сформирован: $REPORT_FILE"
