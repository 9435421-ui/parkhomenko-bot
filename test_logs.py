"""
Тестовый скрипт для проверки отправки сообщений в топик Логов.
"""
import asyncio
import os
import sys

# Добавляем путь для импорта config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import BOT_TOKEN, NOTIFICATIONS_CHANNEL_ID, THREAD_ID_LOGS
from aiogram import Bot


async def test_log_thread():
    """
    Отправляет тестовое сообщение в топик Логов (88).
    """
    if not BOT_TOKEN:
        print("❌ Ошибка: BOT_TOKEN не найден в .env")
        return
        
    bot = Bot(token=BOT_TOKEN)
    
    try:
        # Отправляем сообщение в топик Логов
        message = await bot.send_message(
            chat_id=NOTIFICATIONS_CHANNEL_ID,
            text="Тест связи с Антоном",
            message_thread_id=THREAD_ID_LOGS
        )
        print(f"✅ Сообщение отправлено успешно!")
        print(f"   Chat ID: {NOTIFICATIONS_CHANNEL_ID}")
        print(f"   Thread ID: {THREAD_ID_LOGS}")
        print(f"   Message ID: {message.message_id}")
        
    except Exception as e:
        print(f"❌ Ошибка при отправке сообщения:")
        print(f"   Тип ошибки: {type(e).__name__}")
        print(f"   Причина: {e}")
        
        # Анализ конкретных ошибок
        error_str = str(e)
        if "chat not found" in error_str.lower():
            print("\n💡 Бот не найден в этом чате/канале.")
            print("   Нужно добавить бота в чат как администратора.")
        elif "thread not found" in error_str.lower():
            print("\n💡 Топик с указанным ID не найден.")
            print("   Проверьте правильность THREAD_ID_LOGS в config.py")
        elif "bot is not a member" in error_str.lower():
            print("\n💡 Бот не состоит в этой группе/чате.")
            print("   Нужно добавить бота в группу.")
        elif "have no rights" in error_str.lower() or "rights" in error_str.lower():
            print("\n💡 У бота недостаточно прав для отправки сообщения.")
            print("   Нужно дать боту права администратора или права на отправку сообщений.")
        
    finally:
        await bot.session.close()


if __name__ == "__main__":
    print("=" * 50)
    print("ТЕСТ ОТПРАВКИ СООБЩЕНИЯ В ТОПИК ЛОГОВ")
    print("=" * 50)
    print(f"BOT_TOKEN: {BOT_TOKEN[:10]}..." if BOT_TOKEN else "BOT_TOKEN: None")
    print(f"NOTIFICATIONS_CHANNEL_ID: {NOTIFICATIONS_CHANNEL_ID}")
    print(f"THREAD_ID_LOGS: {THREAD_ID_LOGS}")
    print("=" * 50)
    print()
    
    asyncio.run(test_log_thread())
