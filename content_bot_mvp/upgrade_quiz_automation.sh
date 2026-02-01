#!/bin/bash

# ---------------------------------------------
# Авто-апгрейд квиза проекта ТОРИОН
# ---------------------------------------------

echo "=== 1. Переходим в директорию проекта ==="
cd "$(dirname "$0")"

echo "=== 2. Создаем бэкап текущего quiz.py ==="
# Путь скорректирован Жюлем для соответствия структуре (handlers в корне)
cp ../handlers/quiz.py ../handlers/quiz_backup_$(date +%F_%H-%M-%S).py
echo "Бэкап создан."

echo "=== 3. Вносим ключевые обновления ==="

# 3.1 Ветка для стадии перепланировки
sed -i '/^def handle_quiz_start/,$s/#STAGE_LOGIC/\
if user_stage == "planned":\
    # Контент для планирующих перепланировку\
elif user_stage == "done":\
    # Контент для уже выполненной перепланировки\
/' ../handlers/quiz.py

# 3.2 Добавляем шаг запроса метража помещения
sed -i '/#STAGE_LOGIC/a \
# Запрос метража помещения\
send_message(user_id, "Укажите метраж помещения (м²):")\
user_input = get_user_input()\
save_to_db(user_id, "area", user_input)\
' ../handlers/quiz.py

# 3.3 Обработка медиа (фото/PDF)
sed -i '/#STAGE_LOGIC/a \
# Обработка документов и фото\
if message_has_file():\
    file_path = save_file_to_storage()\
    save_to_db(user_id, "file_path", file_path)\
' ../handlers/quiz.py

# 3.4 Прогресс-бар
sed -i '/#STAGE_LOGIC/a \
# Прогресс-бар\
update_progress_bar(user_id, current_step, total_steps)\
' ../handlers/quiz.py

# 3.5 Персонализация имени
sed -i '/#STAGE_LOGIC/a \
# Персонализация\
send_message(user_id, f"Привет, {user_name}! Продолжаем...")\
' ../handlers/quiz.py

echo "Ключевые исправления внесены."

echo "=== 4. Запуск тестов квиза ==="
if [ -f ../handlers/quiz_test.py ]; then
    python3 -m handlers.quiz_test
    echo "Тесты выполнены."
else
    echo "Файл handlers/quiz_test.py не найден. Пропускаем тесты."
fi

echo "=== 5. Перезапуск бота в фоне ==="
if [ -f ../run_bot.sh ]; then
    chmod +x ../run_bot.sh
    ../run_bot.sh &
    echo "Бот запущен в фоне. Лог: bot.log"
    # tail -n 20 -f ../bot.log # Закомментировано Жюлем для неблокирующего завершения скрипта
else
    echo "run_bot.sh не найден. Бот не запущен."
fi

echo "=== Авто-апгрейд квиза завершен ==="
