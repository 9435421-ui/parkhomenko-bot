#!/bin/bash
# Скрипт инициализации базы данных GEORIS на сервере

cd /root/PARKHOMENKO_BOT || exit 1

# Удаляем старую битую базу
if [ -f "database/bot.db" ]; then
    echo "🗑️  Удаляем старую базу database/bot.db..."
    rm database/bot.db
    echo "✅ Старая база удалена"
fi

# Создаем новую базу через инициализатор проекта
echo "🔧 Инициализируем новую базу данных..."
python3 scripts/init_database.py

if [ $? -eq 0 ]; then
    echo "✅ База данных успешно инициализирована!"
else
    echo "❌ Ошибка инициализации базы данных"
    exit 1
fi
