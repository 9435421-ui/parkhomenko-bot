import logging
import os
from datetime import datetime
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from .discovery import Discovery
from .analyzer import LeadAnalyzer
from .outreach import Outreach
from services.scout_parser import scout_parser
from hunter_standalone import HunterDatabase, LeadHunter as StandaloneLeadHunter

logger = logging.getLogger(__name__)

POTENTIAL_LEADS_DB = os.path.join(os.path.dirname(__file__), "..", "..", "database", "potential_leads.db")


class LeadHunter:
    """Автономный поиск и привлечение клиентов (Lead Hunter)"""

    def __init__(self):
        self.discovery = Discovery()
        self.analyzer = LeadAnalyzer()
        self.outreach = Outreach()
        self.parser = scout_parser  # общий экземпляр: отчёт последнего скана доступен и для /spy_report

    async def _send_hot_lead_to_admin(self, lead: dict):
        """Пересылает горячий лид (AI Жюля, hotness > 4) админу в Telegram."""
        from config import BOT_TOKEN, ADMIN_ID
        if not BOT_TOKEN or not ADMIN_ID:
            logger.warning("⚠️ BOT_TOKEN или ADMIN_ID не заданы — пересылка лида пропущена")
            return
        content = lead.get("content", "") or ""
        text = (
            "🔥 <b>ГОРЯЧИЙ ЛИД (AI Жюля)</b>\n\n"
            f"📄 {content[:500]}{'…' if len(content) > 500 else ''}\n\n"
            f"🎯 Интент: {lead.get('intent', '—')}\n"
            f"⭐ Горячность: {lead.get('hotness', 0)}\n"
            f"📍 Гео: {lead.get('geo', '—')}\n"
            f"💡 Контекст: {lead.get('context_summary', '—')}\n\n"
            f"🔗 {lead.get('url', '')}"
        )
        try:
            bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            await bot.send_message(ADMIN_ID, text)
            await bot.session.close()
        except Exception as e:
            logger.error(f"❌ Не удалось отправить горячий лид админу: {e}")

    async def hunt(self):
        """Полный цикл: поиск → анализ → привлечение + проверка через AI Жюля и пересылка горячих лидов."""
        logger.info("🏹 LeadHunter: начало охоты за лидами...")

        self.parser.last_scan_report = []
        self.parser.last_scan_at = datetime.now()

        tg_posts = await self.parser.parse_telegram()
        vk_posts = await self.parser.parse_vk()
        all_posts = tg_posts + vk_posts

        for post in all_posts:
            score = await self.analyzer.analyze_post(post.text)
            if score > 0.7:
                logger.info(f"🎯 Найден горячий лид! Score: {score}")
                message = self.parser.generate_outreach_message(post.source_type)
                await self.outreach.send_offer(post.source_type, post.source_id, message)

        if all_posts:
            messages = [
                {"text": p.text, "url": p.url or f"{p.source_type}/{p.source_id}/{p.post_id}"}
                for p in all_posts
            ]
            db_path = os.path.abspath(POTENTIAL_LEADS_DB)
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            try:
                db = HunterDatabase(db_path)
                await db.connect()
                standalone = StandaloneLeadHunter(db)
                hot_leads = await standalone.hunt(messages)
                if db.conn:
                    await db.conn.close()
                for lead in hot_leads:
                    if lead.get("hotness", 0) > 4:
                        logger.info(f"🔥 Горячий лид (Жюль, hotness={lead.get('hotness')}) → пересылка админу")
                        await self._send_hot_lead_to_admin(lead)
            except Exception as e:
                logger.error(f"❌ Ошибка hunter_standalone (AI Жюля): {e}")

        # Отчёт в рабочую группу: где был шпион, в какие группы/каналы удалось попасть
        try:
            from config import BOT_TOKEN, LEADS_GROUP_CHAT_ID, THREAD_ID_LOGS
            report = self.parser.get_last_scan_report()
            if BOT_TOKEN and LEADS_GROUP_CHAT_ID and report and "Отчёта ещё нет" not in report:
                bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
                await bot.send_message(
                    LEADS_GROUP_CHAT_ID,
                    report,
                    message_thread_id=THREAD_ID_LOGS,
                )
                await bot.session.close()
        except Exception as e:
            logger.warning("Не удалось отправить отчёт шпиона в группу: %s", e)

        logger.info(f"🏹 LeadHunter: охота завершена. Обработано {len(all_posts)} постов.")
