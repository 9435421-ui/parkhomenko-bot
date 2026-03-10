import asyncio
import logging
import os
import sys
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telethon import TelegramClient
from config import API_ID, API_HASH, BOT_TOKEN, LEADS_GROUP_CHAT_ID
from services.scout_parser import ScoutParser

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("bot_spy")

class BotSpy:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.parser = ScoutParser()
        self.bot_token = BOT_TOKEN
        self.chat_id = LEADS_GROUP_CHAT_ID

    async def send_telegram_msg(self, text: str):
        """Отправка сообщения через Bot API (не требует авторизации Telethon)"""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        logger.error(f"Error sending message: {await resp.text()}")
                    else:
                        logger.info("✅ Message sent successfully via Bot API")
            except Exception as e:
                logger.error(f"Exception sending message: {e}")

    async def hunt_job(self):
        logger.info("🚀 Starting hunt job...")
        try:
            # Сканируем только ВК (Telegram сканирование пропускаем из-за отсутствия авторизации)
            leads = await self.parser.scan_vk_groups()
            if leads:
                # Отправляем результаты в LeadHunter для анализа и отправки карточек
                # Импортируем здесь, чтобы избежать циклических зависимостей
                from services.lead_hunter.hunter import LeadHunter
                hunter = LeadHunter()
                await hunter.process_leads(leads)
                logger.info(f"✅ Hunt complete, found {len(leads)} leads")
            else:
                logger.info("✅ Hunt complete, no new leads")
        except Exception as e:
            logger.error(f"❌ Error in hunt job: {e}")

    async def start(self):
        logger.info("🎯 Starting Bot Spy Demon...")
        # Не запускаем Telegram-клиент, так как он не авторизован
        # await self.parser.start()
        
        # Запуск охоты каждые 30 минут, только один экземпляр одновременно
        self.scheduler.add_job(self.hunt_job, 'interval', minutes=30, max_instances=1)
        self.scheduler.start()
        
        # Первая охота при запуске
        await self.hunt_job()
        
        try:
            while True:
                await asyncio.sleep(3600)
        except (KeyboardInterrupt, asyncio.CancelledError):
            await self.stop()

    async def stop(self):
        logger.info("🛑 Stopping Bot Spy...")
        self.scheduler.shutdown()
        # await self.parser.stop()

async def start_spy_bot():
    """Главная функция запуска шпиона для импорта в watchdog."""
    spy = BotSpy()
    try:
        await spy.start()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    try:
        asyncio.run(start_spy_bot())
    except KeyboardInterrupt:
        pass
