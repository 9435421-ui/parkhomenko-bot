#!/bin/bash
# upgrade_quiz_automation.sh — Патчер логики квиза ТОРИОН (Идемпотентный)

QUIZ_FILE="../handlers/quiz.py"

echo "[AUTO] Начало патчинга $QUIZ_FILE..."

# 1. Внедряем генератор прогресс-бара
if ! grep -q "def get_progress_bar" "$QUIZ_FILE"; then
    sed -i '/import re/a \
\
def get_progress_bar(step, total=10):\
    return f"📊 Шаг {step} из {total}\\n" + "—" * 20 + "\\n"' "$QUIZ_FILE"
    echo "Added get_progress_bar"
fi

# 2. Обновляем STAGE_LOGIC
if grep -q "# STAGE_LOGIC" "$QUIZ_FILE"; then
    sed -i '/# STAGE_LOGIC/c \    # Внедренная логика ветвления\
    if user_stage == "planned":\
        print("Ветка: Чек-лист")\
    else:\
        print("Ветка: Легализация")' "$QUIZ_FILE"
    echo "Updated STAGE_LOGIC"
fi

# 3. Добавляем шаг метража в StatesGroup (если его там нет)
if ! grep -q "area = State()" "$QUIZ_FILE"; then
    sed -i '/obj_type = State()/a \    area = State()' "$QUIZ_FILE"
    echo "Added area state"
fi

# 4. Обновляем уведомление админа (проверяем наличие метража в summary)
# Если метраж уже есть в summary, не добавляем
if ! grep -q "📐 <b>Метраж:</b>" "$QUIZ_FILE"; then
    sed -i 's/🏙 <b>Город:<\/b> {data.get('\''city'\'')}/🏙 <b>Город:<\/b> {data.get('\''city'\'')}\\n        f"📐 <b>Метраж:<\/b> {data.get('\''area'\'')} м²/' "$QUIZ_FILE"
    echo "Added meterage to summary"
fi

echo "[AUTO] Патчинг завершен."
