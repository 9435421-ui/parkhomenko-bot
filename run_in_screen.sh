#!/bin/bash
# Запуск бота в новой сессии screen
screen -dmS terion_bot bash -c "source venv/bin/activate && python3 main.py"
echo "Бот запущен в сессии screen 'terion_bot'."
echo "Чтобы подключиться: screen -r terion_bot"
echo "Чтобы выйти из сессии (не выключая бота): Ctrl+A, потом D"
