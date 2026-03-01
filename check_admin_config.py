#!/usr/bin/env python3
"""
Скрипт для проверки конфигурации админов.
Показывает текущие настройки ADMIN_ID и JULIA_USER_ID.
"""
import os
from dotenv import load_dotenv

load_dotenv()

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
JULIA_USER_ID = int(os.getenv("JULIA_USER_ID", "0"))

print("=" * 50)
print("ПРОВЕРКА КОНФИГУРАЦИИ АДМИНОВ")
print("=" * 50)
print(f"\nADMIN_ID: {ADMIN_ID}")
print(f"JULIA_USER_ID: {JULIA_USER_ID}")
print("\n" + "=" * 50)

if ADMIN_ID == 0:
    print("⚠️  ADMIN_ID не задан (равен 0)")
else:
    print(f"✅ ADMIN_ID настроен: {ADMIN_ID}")

if JULIA_USER_ID == 0:
    print("⚠️  JULIA_USER_ID не задан (равен 0)")
    print("\n📝 Для добавления ID Юлии в .env добавьте строку:")
    print("   JULIA_USER_ID=8438024806")
else:
    print(f"✅ JULIA_USER_ID настроен: {JULIA_USER_ID}")

print("\n" + "=" * 50)
print("После изменения .env перезапустите бота:")
print("   pm2 restart anton-2-bot")
print("=" * 50)
