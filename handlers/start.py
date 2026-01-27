from aiogram import Router, F
from aiogram.types import Message

router = Router()

@router.message(F.text.startswith("/start"))
async def handle_start(message: Message):
    payload = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""

    if payload == "quiz":
        await message.answer("Запускаем опрос: квалификация объекта...")
        # Здесь будет запуск FSM-опроса
    elif payload == "invest":
        await message.answer("Открываю инвест-калькулятор: оценим прибыльность...")
        # Здесь будет запуск калькулятора
    elif payload == "ask":
        await message.answer("Я готов ответить на ваши вопросы по перепланировке. Что вас интересует?")
        # Здесь будет активация RAG
    else:
        await message.answer(
            "Здравствуйте! Я Антон — ИИ-помощник эксперта Пархоменко Юлии Владимировны.\n"
            "Моя специализация — капитализация недвижимости через законную перепланировку.\n"
            "С Антоном всё будет в ладу: и стены, и документы.\n\n"
            "Выберите, с чего начнем:",
            reply_markup=get_main_menu()
        )
