import asyncio
import logging
import os
from dotenv import load_dotenv

# Загружаем переменные окружения ДО импорта агента
load_dotenv()

from agents.creative_agent import creative_agent

logging.basicConfig(level=logging.INFO)

async def main():
    print("\n--- SCOUTING TOPICS ---")
    topics = await creative_agent.scout_topics(3)
    if not topics:
        print("[ERROR] No topics generated.")
        return
    
    for i, topic in enumerate(topics, 1):
        print(f"\n{i}. {topic.get('title')}")
        print(f"   Insight: {topic.get('insight')}")

if __name__ == "__main__":
    asyncio.run(main())
