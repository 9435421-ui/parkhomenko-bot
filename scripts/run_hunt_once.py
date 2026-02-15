#!/usr/bin/env python3
"""
Принудительный запуск охоты за лидами (один раз).
Использование: из корня проекта
  ./venv/bin/python scripts/run_hunt_once.py
  cd /root/PARKHOMENKO_BOT && ./venv/bin/python scripts/run_hunt_once.py
"""
import asyncio
import sys
import os

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)
os.chdir(root)

from dotenv import load_dotenv
load_dotenv()

async def main():
    from database import db
    from services.lead_hunter import LeadHunter

    await db.connect()
    hunter = LeadHunter()
    print("🏹 Запуск охоты за лидами...")
    await hunter.hunt()
    print("✅ Охота завершена.")
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
