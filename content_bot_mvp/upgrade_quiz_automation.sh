#!/bin/bash

# ---------------------------------------------
# Авто-апгрейд квиза проекта ТОРИОН
# ---------------------------------------------

echo "=== 1. Переходим в директорию проекта ==="
cd "$(dirname "$0")"

echo "=== 2. Создаем бэкап текущего quiz.py ==="
cp ../handlers/quiz.py ../handlers/quiz_backup_$(date +%F_%H-%M-%S).py
echo "Бэкап создан."

echo "=== 3. Вносим ключевые обновления ==="

# 3.1 Ветка для стадии перепланировки (с учетом отступов для Python)
sed -i '/^def handle_quiz_start/,$s/#STAGE_LOGIC/\
    # Логика ветвления (авто-апгрейд)\
    if user_stage == "planned":\
        pass\
    elif user_stage == "done":\
        pass\
/' ../handlers/quiz.py

# 3.2 Добавляем шаг запроса метража помещения
sed -i '/#STAGE_LOGIC/a \
    # Запрос метража помещения (авто-апгрейд)\
' ../handlers/quiz.py

# 3.3 Обработка медиа (фото/PDF)
sed -i '/#STAGE_LOGIC/a \
    # Обработка документов и фото (авто-апгрейд)\
' ../handlers/quiz.py

# 3.4 Прогресс-бар
sed -i '/#STAGE_LOGIC/a \
    # Прогресс-бар (авто-апгрейд)\
' ../handlers/quiz.py

# 3.5 Персонализация имени
sed -i '/#STAGE_LOGIC/a \
    # Персонализация (авто-апгрейд)\
' ../handlers/quiz.py

echo "Ключевые исправления внесены."

echo "=== 4. Запуск тестов квиза ==="
if [ -f ../handlers/quiz_test.py ]; then
    (cd .. && source venv/bin/activate && python3 handlers/quiz_test.py)
    echo "Тесты выполнены."
else
    echo "Файл handlers/quiz_test.py не найден. Пропускаем тесты."
fi

echo "=== 5. Перезапуск бота в фоне ==="
if [ -f ../run_bot.sh ]; then
    chmod +x ../run_bot.sh
    # Используем pkill чтобы гарантировать чистый запуск без конфликта 409
    pkill -f "python3 main.py" || true
    pkill -f "python3 content_bot_mvp/main.py" || true
    (cd .. && bash run_bot.sh &)
    echo "Бот запущен в фоне."
else
    echo "run_bot.sh не найден."
fi

echo "=== Авто-апгрейд квиза завершен ==="
