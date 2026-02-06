#!/bin/bash

# Скрипт быстрого запуска бота «Лад в квартире»

set -e

echo "🚀 Запуск бота «Лад в квартире»..."
echo ""

# Проверка существования .env
if [ ! -f .env ]; then
    echo "❌ Файл .env не найден!"
    echo "📝 Создайте .env из .env.example и заполните необходимые поля"
    echo ""
    echo "Команды:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi

# Проверка Docker
if command -v docker &> /dev/null && command -v docker compose &> /dev/null; then
    echo "🐳 Docker обнаружен. Запуск через Docker..."
    echo ""

    # Остановка существующих контейнеров
    docker compose down 2>/dev/null || true

    # Сборка и запуск
    docker compose up -d --build

    echo ""
    echo "✅ Бот запущен в Docker контейнере!"
    echo ""
    echo "📊 Полезные команды:"
    echo "  docker compose logs -f bot     - просмотр логов"
    echo "  docker compose ps              - статус контейнера"
    echo "  docker compose down            - остановить бота"
    echo "  docker compose restart         - перезапустить бота"
    echo ""

    # Показываем логи
    echo "📋 Последние 20 строк логов:"
    docker compose logs --tail=20 bot

elif command -v python3.11 &> /dev/null || command -v python3 &> /dev/null; then
    echo "🐍 Python обнаружен. Запуск напрямую..."
    echo ""

    # Определяем команду Python
    if command -v python3.11 &> /dev/null; then
        PYTHON_CMD=python3.11
    else
        PYTHON_CMD=python3
    fi

    # Проверка/создание виртуального окружения
    if [ ! -d "venv" ]; then
        echo "📦 Создание виртуального окружения..."
        $PYTHON_CMD -m venv venv
    fi

    # Активация виртуального окружения
    source venv/bin/activate

    # Установка зависимостей
    echo "📥 Установка зависимостей..."
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt

    echo ""
    echo "✅ Запуск бота..."
    echo ""

    # Запуск бота
    python bot.py

else
    echo "❌ Ни Docker, ни Python не найдены!"
    echo ""
    echo "Установите одно из:"
    echo "  - Docker: curl -fsSL https://get.docker.com | sh"
    echo "  - Python 3.11: sudo apt install python3.11"
    exit 1
fi
