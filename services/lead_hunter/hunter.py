import io
import logging
import os
from datetime import datetime
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BufferedInputFile

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

    def _format_lead_card(self, lead: dict) -> str:
        """Форматирует одну карточку лида для отправки в группу."""
        content = (lead.get("content") or lead.get("intent") or "")[:600]
        if len(lead.get("content") or "") > 600:
            content += "…"
        return (
            "🕵️ <b>Карточка лида (шпион)</b>\n\n"
            f"📄 {content}\n\n"
            f"🎯 <b>Интент:</b> {lead.get('intent', '—')}\n"
            f"⭐ <b>Горячность:</b> {lead.get('hotness', 0)}/10\n"
            f"📍 <b>Гео:</b> {lead.get('geo', '—')}\n"
            f"💡 <b>Контекст:</b> {lead.get('context_summary', '—')}\n\n"
            f"🔗 {lead.get('url', '')}"
        )

    async def _send_lead_card_to_group(self, lead: dict) -> bool:
        """Отправляет карточку лида в рабочую группу (топик «Горячие лиды»)."""
        from config import BOT_TOKEN, LEADS_GROUP_CHAT_ID, THREAD_ID_HOT_LEADS
        if not BOT_TOKEN or not LEADS_GROUP_CHAT_ID:
            logger.warning("⚠️ BOT_TOKEN или LEADS_GROUP_CHAT_ID не заданы — карточка в группу не отправлена")
            return False
        text = self._format_lead_card(lead)
        try:
            bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            thread_id = THREAD_ID_HOT_LEADS if THREAD_ID_HOT_LEADS else None
            await bot.send_message(
                LEADS_GROUP_CHAT_ID,
                text,
                message_thread_id=thread_id,
            )
            await bot.session.close()
            return True
        except Exception as e:
            logger.error("❌ Не удалось отправить карточку лида в группу: %s", e)
            return False

    def _build_raw_leads_file(self, all_posts: list, max_entries: int = 1000) -> bytes:
        """Собирает текстовый файл со списком лидов: источник | превью текста | ссылка."""
        lines = [
            "Лиды шпиона (последний скан)",
            f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            f"Всего постов с ключевыми словами: {len(all_posts)}",
            "",
            "---",
            "",
        ]
        for i, post in enumerate(all_posts[:max_entries], 1):
            source = getattr(post, "source_name", post.source_id) if hasattr(post, "source_name") else post.source_id
            text_preview = (post.text or "").replace("\n", " ").strip()[:400]
            url = getattr(post, "url", "") or f"{post.source_type}/{post.source_id}/{post.post_id}"
            lines.append(f"[{i}] {source}")
            lines.append(f"Текст: {text_preview}")
            lines.append(f"Ссылка: {url}")
            lines.append("")
        if len(all_posts) > max_entries:
            lines.append(f"... и ещё {len(all_posts) - max_entries} лидов (обрезано).")
        return "\n".join(lines).encode("utf-8")

    async def _send_raw_leads_file_to_group(self, all_posts: list) -> bool:
        """Отправляет в рабочую группу файл со списком всех лидов (источник, превью, ссылка)."""
        from config import BOT_TOKEN, LEADS_GROUP_CHAT_ID, THREAD_ID_LOGS
        if not BOT_TOKEN or not LEADS_GROUP_CHAT_ID:
            return False
        try:
            file_bytes = self._build_raw_leads_file(all_posts)
            filename = f"scout_leads_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.txt"
            doc = BufferedInputFile(file_bytes, filename=filename)
            bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            await bot.send_document(
                LEADS_GROUP_CHAT_ID,
                doc,
                caption=f"📎 Список лидов по скану ({len(all_posts)} постов с ключевыми словами). Источник, превью текста, ссылка.",
                message_thread_id=THREAD_ID_LOGS,
            )
            await bot.session.close()
            logger.info("📎 Файл со списком лидов отправлен в группу (топик Логи)")
            return True
        except Exception as e:
            logger.warning("Не удалось отправить файл лидов в группу: %s", e)
            return False

    async def _send_lead_notify_to_admin(self, lead: dict, source_name: str = "", profile_url: str = ""):
        """При нахождении лида — уведомление в личку админу (Юлия, ADMIN_ID)."""
        from config import BOT_TOKEN, ADMIN_ID
        if not BOT_TOKEN or not ADMIN_ID:
            return
        content = (lead.get("content") or lead.get("intent") or "")[:300]
        text = (
            "🕵️ <b>Новый лид (шпион)</b>\n\n"
            f"📄 {content}{'…' if len(lead.get('content') or '') > 300 else ''}\n\n"
            f"📍 Источник: {source_name or '—'}\n"
            f"⭐ Горячность: {lead.get('hotness', 0)}/10\n"
        )
        if profile_url:
            text += f"🔗 Профиль/пост: {profile_url}\n"
        else:
            text += f"🔗 {lead.get('url', '')}\n"
        try:
            bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            await bot.send_message(ADMIN_ID, text)
            await bot.session.close()
        except Exception as e:
            logger.debug("Уведомление админу о лиде: %s", e)

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

        tg_ok = [r for r in (self.parser.last_scan_report or []) if r.get("type") == "telegram" and r.get("status") == "ok"]
        vk_ok = [r for r in (self.parser.last_scan_report or []) if r.get("type") == "vk" and r.get("status") == "ok"]
        logger.info(
            "🔍 ScoutParser: просканировано TG каналов=%s, VK групп=%s, постов с ключевыми словами=%s",
            len(tg_ok), len(vk_ok), len(all_posts)
        )

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
                # Максимум карточек в группу за один запуск (чтобы не флудить)
                MAX_CARDS_PER_RUN = 30
                cards_sent = 0
                # Сопоставление hot_lead с постом по url для author_id/username/profile_url
                def find_post_by_url(url: str):
                    for p in all_posts:
                        post_url = getattr(p, "url", "") or f"{p.source_type}/{p.source_id}/{p.post_id}"
                        if post_url == url or url in post_url:
                            return p
                    return None

                for lead in hot_leads:
                    if lead.get("hotness", 0) > 4:
                        logger.info(f"🔥 Горячий лид (Жюль, hotness={lead.get('hotness')}) → пересылка админу")
                        await self._send_hot_lead_to_admin(lead)
                    # Сохраняем лид в spy_leads (user_id, username, ссылка на профиль)
                    post = find_post_by_url(lead.get("url", ""))
                    author_id = getattr(post, "author_id", None) if post else None
                    author_name = getattr(post, "author_name", None) if post else None
                    source_name = getattr(post, "source_name", "") if post else "—"
                    source_type = getattr(post, "source_type", "telegram") if post else "telegram"
                    profile_url = ""
                    if author_id is not None and source_type == "vk":
                        aid = int(author_id) if isinstance(author_id, (int, str)) and str(author_id).lstrip("-").isdigit() else 0
                        if aid > 0:  # пользователь, не группа
                            profile_url = f"https://vk.com/id{aid}"
                    elif author_id is not None and source_type == "telegram":
                        profile_url = f"tg://user?id={author_id}"
                    try:
                        from database import db as main_db
                        await main_db.add_spy_lead(
                            source_type=source_type,
                            source_name=source_name,
                            url=lead.get("url", ""),
                            text=(lead.get("content") or lead.get("intent") or "")[:2000],
                            author_id=str(author_id) if author_id else None,
                            username=author_name,
                            profile_url=profile_url or None,
                        )
                    except Exception as e:
                        logger.warning("Не удалось сохранить spy_lead: %s", e)
                    # Уведомление в личку админу (Юлия) при каждом лиде (если включено в пульте)
                    try:
                        from database import db as main_db
                        notify_enabled = await main_db.get_setting("spy_notify_enabled", "1")
                        if notify_enabled == "1":
                            await self._send_lead_notify_to_admin(lead, source_name, profile_url or lead.get("url", ""))
                    except Exception:
                        pass
                    # Карточка лида в рабочую группу (топик «Горячие лиды»)
                    if cards_sent < MAX_CARDS_PER_RUN:
                        if await self._send_lead_card_to_group(lead):
                            cards_sent += 1
                if cards_sent:
                    logger.info("📋 В рабочую группу отправлено карточек лидов: %s", cards_sent)
                # Дублирование в рабочую группу: краткий отчёт о сохранённых лидах
                if hot_leads:
                    from config import BOT_TOKEN, LEADS_GROUP_CHAT_ID, THREAD_ID_LOGS
                    if BOT_TOKEN and LEADS_GROUP_CHAT_ID:
                        try:
                            bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
                            summary = f"🕵️ <b>Охота: в potential_leads сохранено {len(hot_leads)} лидов</b>"
                            if cards_sent:
                                summary += f", в топик «Горячие лиды» отправлено карточек: {cards_sent}"
                            summary += "\n\n"
                            for i, lead in enumerate(hot_leads[:3], 1):
                                content = (lead.get("content") or lead.get("intent") or "")[:80]
                                summary += f"{i}. {content}…\n"
                            await bot.send_message(
                                LEADS_GROUP_CHAT_ID,
                                summary,
                                message_thread_id=THREAD_ID_LOGS,
                            )
                            await bot.session.close()
                        except Exception as e:
                            logger.warning("Не удалось отправить сводку лидов в группу: %s", e)
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

        # Файл со списком всех лидов (источник, превью текста, ссылка) — в тот же топик «Логи»
        if all_posts:
            await self._send_raw_leads_file_to_group(all_posts)

        logger.info(f"🏹 LeadHunter: охота завершена. Обработано {len(all_posts)} постов.")
