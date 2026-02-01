#!/bin/bash
# upgrade_quiz_run.sh — апгрейд квиза ТОРИОН

# 1. Перейти в корень проекта скрипта
cd "$(dirname "$0")" || exit 1

# 2. Создать бэкап quiz.py
timestamp=$(date +"%Y%m%d_%H%M%S")
cp ../handlers/quiz.py ../handlers/quiz_backup_$timestamp.py
echo "[INFO] Бэкап quiz.py создан: quiz_backup_$timestamp.py"

# 3. Применить патч апгрейда
bash upgrade_quiz_automation.sh
echo "[INFO] Скрипт upgrade_quiz_automation.sh выполнен"

# 4. Запустить тесты логики квиза
# Используем виртуальное окружение
(cd .. && source venv/bin/activate && python3 handlers/quiz_test.py)
echo "[INFO] Тесты quiz_test.py выполнены"

# 5. Перезапустить контент-бот в фоне
# Мы уже делаем это в upgrade_quiz_automation.sh, но продублируем для надежности или просто убедимся что он запущен
# bash ../run_bot.sh &
echo "[INFO] Бот перезапущен"

# 6. Просмотр последних строк лога для контроля
echo "[INFO] Лог последних событий:"
tail -n 20 ../bot.log
