#!/bin/bash
# ===========================
# Скрипт автоматизации обновления и тестирования квиза ТОРИОН
# ===========================

# --- Настройка переменных (относительно директории скрипта) ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOT_DIR="$(dirname "$SCRIPT_DIR")" # Корень проекта

BACKUP_DIR="$BOT_DIR/backups"
QUIZ_FILE="$BOT_DIR/handlers/quiz.py"
TEST_FILE="$BOT_DIR/handlers/quiz_test.py"
RUN_SCRIPT="$BOT_DIR/run_bot.sh"
LOG_FILE="$BOT_DIR/bot.log"
ERROR_LOG="$BOT_DIR/bot_error_log.txt"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "--- Запуск автоматизации для проекта ТОРИОН ---"

# --- 1. Резервное копирование квиза ---
mkdir -p "$BACKUP_DIR"
if [ -f "$QUIZ_FILE" ]; then
    cp "$QUIZ_FILE" "$BACKUP_DIR/quiz_backup_$TIMESTAMP.py"
    echo "[INFO] Резервная копия создана: $BACKUP_DIR/quiz_backup_$TIMESTAMP.py"
else
    echo "[ERROR] Файл квиза не найден: $QUIZ_FILE"
    exit 1
fi

# --- 2. Применение патчера (идемпотентно) ---
if [ -f "$SCRIPT_DIR/upgrade_quiz_automation.sh" ]; then
    bash "$SCRIPT_DIR/upgrade_quiz_automation.sh"
    echo "[INFO] Патчер логики квиза выполнен."
else
    echo "[WARNING] Файл upgrade_quiz_automation.sh не найден в $SCRIPT_DIR. Пропуск патчинга."
fi

# --- 3. Тестирование логики квиза ---
if [ -f "$TEST_FILE" ]; then
    # Активируем venv если он есть
    if [ -d "$BOT_DIR/venv" ]; then
        source "$BOT_DIR/venv/bin/activate"
    fi

    python3 "$TEST_FILE"
    TEST_RESULT=$?

    if [ $TEST_RESULT -eq 0 ]; then
        echo "[INFO] Тесты пройдены успешно."
    else
        echo "[ERROR] Тесты выявили ошибки. Проверьте $TEST_FILE"
        exit 1
    fi
else
    echo "[WARNING] Файл тестов не найден: $TEST_FILE. Пропуск тестирования."
fi

# --- 4. Перезапуск бота ---
if [ -f "$RUN_SCRIPT" ]; then
    # Убеждаемся, что мы в корне для запуска run_bot.sh
    cd "$BOT_DIR"
    bash "$RUN_SCRIPT" &
    echo "[INFO] Бот перезапущен в фоне."
else
    echo "[ERROR] Скрипт запуска run_bot.sh не найден в $BOT_DIR!"
    exit 1
fi

# --- 5. Вывод последних строк логов ---
echo "--- Последние 10 строк лога ($LOG_FILE) ---"
touch "$LOG_FILE" # Убеждаемся что файл существует
tail -n 10 "$LOG_FILE"

echo "--- Последние 10 строк ошибок ($ERROR_LOG) ---"
touch "$ERROR_LOG"
tail -n 10 "$ERROR_LOG"

echo "[INFO] Обновление и тестирование завершены."
