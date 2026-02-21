import io
import logging
import os
import json
import re
from datetime import datetime
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton

from .discovery import Discovery
from .outreach import Outreach
from services.scout_parser import scout_parser
from database import db as main_db

logger = logging.getLogger(__name__)


def _bot_for_send():
    """Единый источник: бот из main.py через utils.bot_config.get_main_bot()."""
    try:
        from utils.bot_config import get_main_bot
        return get_main_bot()
    except Exception:
        return None


class LeadHunter:
    """Автономный поиск и привлечение клиентов (Lead Hunter) v3.1 (Fixed & Stable)"""

    def __init__(self):
        self.discovery = Discovery()
        self.outreach = Outreach()
        self.parser = scout_parser

    def _format_lead_card(
        self,
        lead: dict,
        profile_url: str = "",
        card_header: str = "",
        anton_recommendation: str = "",
    ) -> str:
        """Форматирует карточку лида."""
        recommendation = (lead.get("recommendation") or anton_recommendation or "").strip()
        pain_level = lead.get("pain_level") or min(lead.get("hotness", 3), 5)
        pain_stage = lead.get("pain_stage")

        if pain_stage == "ST-4" or (recommendation and pain_level >= 4):
            return self._format_lead_card_v2(lead, profile_url, card_header, recommendation, pain_level)

        content = (lead.get("content") or lead.get("intent") or "")[:600]
        if len(lead.get("content") or "") > 600:
            content += "…"
        lines = []
        if card_header:
            lines.append(f"🏢 <b>{card_header}</b>")
            lines.append("")
        lines.extend([
            "🕵️ <b>Карточка лида</b>",
            "",
            f"📄 {content}",
            "",
            f"🎯 <b>Интент:</b> {lead.get('intent', '—')}",
            f"⭐ <b>Горячность:</b> {lead.get('hotness', 0)}/10",
            f"📍 <b>Гео:</b> {lead.get('geo', '—')}",
            f"💡 <b>Контекст:</b> {lead.get('context_summary', '—')}",
        ])
        if pain_stage:
            lines.append(f"🔴 <b>Стадия боли:</b> {pain_stage}")
        if anton_recommendation:
            lines.append(f"💡 <b>Рекомендация Антона:</b> {anton_recommendation}")
        if profile_url and profile_url.startswith("tg://"):
            lines.append(f"\n👤 <b>Профиль:</b> <code>{profile_url}</code>")
        lines.append(f"\n🔗 Пост: {lead.get('url', '')}")
        return "\n".join(lines)

    def _format_lead_card_v2(
        self,
        lead: dict,
        profile_url: str = "",
        card_header: str = "",
        recommendation: str = "",
        pain_level: int = 3,
    ) -> str:
        """Формат карточки Умный Охотник v2.0: ГОРЯЧИЙ ЛИД, цитата, аналитика, вердикт."""
        source = card_header or "Чат ЖК"
        pain_stage = lead.get("pain_stage")

        client_line = "👤 <b>Клиент:</b> "
        if profile_url and profile_url.startswith("http"):
            client_line += f'<a href="{profile_url}">профиль</a>'
        elif profile_url and profile_url.startswith("tg://"):
            client_line += f"<code>{profile_url}</code>"
        else:
            client_line += "—"
        quote = (lead.get("content") or lead.get("intent") or "")[:400]
        if len(lead.get("content") or "") > 400:
            quote += "…"
        pain_label = "Критично" if pain_level >= 4 or pain_stage == "ST-4" else "Высокая" if pain_level >= 3 else "Средняя"

        header = f"🔥 <b>ГОРЯЧИЙ ЛИД:</b> {source}"
        urgency_note = ""
        if pain_stage == "ST-4":
            header = f"🚨 <b>СРОЧНЫЙ ВЫЕЗД/ЗВОНОК:</b> {source}"
            urgency_note = "\n⚠️ <b>Почему это важно:</b> У клиента риск судебного иска или предписания!"

        lines = [
            header,
            urgency_note,
            "",
            client_line,
            f"📝 <b>Цитата:</b> «{quote}»",
            "",
            "🎯 <b>Аналитика Антона:</b>",
            f"Уровень боли: {pain_level}/5 ({pain_label})",
            f"Стадия: {pain_stage or '—'}",
            f"<b>Вердикт:</b> {recommendation[:500]}",
            "",
            f"🔗 Пост: {lead.get('url', '')}",
        ]
        return "\n".join(lines)

    async def _analyze_lead(self, text: str) -> dict:
        """Единый AI-анализ: объединяет LeadAnalyzer и IntentAnalyzer."""
        if not text or len(text.strip()) < 10:
            return {"is_lead": False}

        system_prompt = (
            "Ты — ведущий эксперт компании TERION (согласование перепланировок в Москве). "
            "Проанализируй сообщение и классифицируй его.\n"
            "Стадии боли:\n"
            "- ST-1 (Инфо): теоритические вопросы.\n"
            "- ST-2 (Планирование): собирается делать ремонт.\n"
            "- ST-3 (Актив): уже делает ремонт, ищет как узаконить.\n"
            "- ST-4 (Критично): предписание, инспекция, суд, блокировка сделки.\n\n"
            "Верни ТОЛЬКО JSON: {is_lead, intent, hotness (1-10), pain_stage, pain_level (1-5), geo, context_summary, recommendation}"
        )

        try:
            from utils.router_ai import router_ai
            response = await router_ai.generate_response(f"{system_prompt}\n\nТекст: \"{text}\"", model="kimi")
            if response:
                match = re.search(r'\{[\s\S]*\}', response)
                if match:
                    data = json.loads(match.group(0))
                    data["is_lead"] = data.get("is_lead", False) or data.get("hotness", 0) >= 5
                    return data
        except Exception as e:
            logger.error(f"AI Analysis error: {e}")

        # Fallback
        t_l = text.lower()
        if any(k in t_l for k in ["перепланиров", "узакон", "мжи", "снос"]):
            return {
                "is_lead": True, "intent": "Запрос по перепланировке", "hotness": 7,
                "pain_stage": "ST-3" if "мжи" in t_l else "ST-2", "pain_level": 3
            }
        return {"is_lead": False}

    async def hunt(self):
        """Оптимизированный цикл охоты."""
        logger.info("🏹 LeadHunter v3.1: начало охоты...")

        # Очистка кеша
        try:
            self.parser.last_scan_report = []
            self.parser.last_scan_at = datetime.now()
        except Exception:
            pass

        # Сбор постов
        try:
            tg_posts = await self.parser.parse_telegram(db=main_db)
            vk_posts = await self.parser.parse_vk(db=main_db)
            all_posts = tg_posts + vk_posts
        except Exception as e:
            logger.error(f"Error during scan: {e}")
            return

        if not all_posts:
            logger.info("🔎 Лидов не найдено. Запуск Discovery...")
            try:
                new_sources = await self.discovery.find_new_sources()
                for src in new_sources:
                    await main_db.add_target_resource(src.get("source_type", "telegram"), src["link"], title=src.get("title", "—"), status="pending")
            except Exception:
                pass
            return

        MAX_CARDS_PER_RUN = 30
        cards_sent = 0

        for post in all_posts:
            try:
                analysis = await self._analyze_lead(post.text)
                if not analysis.get("is_lead"):
                    continue

                # Сохраняем в основную БД
                author_id = getattr(post, "author_id", None)
                source_type = getattr(post, "source_type", "telegram")
                profile_url = ""
                if author_id:
                    if source_type == "vk": profile_url = f"https://vk.com/id{author_id}"
                    else: profile_url = f"tg://user?id={author_id}"

                post_url = getattr(post, "url", "") or f"{source_type}/{post.source_id}/{post.post_id}"

                lead_id = await main_db.add_spy_lead(
                    source_type=source_type,
                    source_name=getattr(post, "source_name", "—"),
                    url=post_url,
                    text=post.text[:2000],
                    author_id=str(author_id) if author_id else None,
                    username=getattr(post, "author_name", None),
                    profile_url=profile_url,
                    pain_stage=analysis.get("pain_stage"),
                    priority_score=analysis.get("hotness", 5)
                )

                # Карточка в группу
                if cards_sent < MAX_CARDS_PER_RUN:
                    card_header = getattr(post, "source_name", "Чат ЖК")
                    # Пытаемся получить гео из БД
                    try:
                        res = await main_db.get_target_resource_by_link(getattr(post, "source_link", ""))
                        if res: card_header = res.get("geo_tag") or res.get("title") or card_header
                    except Exception:
                        pass

                    if await self._send_lead_card_to_group(analysis, lead_id, profile_url, post_url, card_header):
                        cards_sent += 1

                # Уведомление админу если горячий
                if analysis.get("hotness", 0) >= 8 or analysis.get("pain_stage") == "ST-4":
                    await self._send_hot_lead_to_admin({**analysis, "content": post.text, "url": post_url})
            except Exception as e:
                logger.warning(f"Error processing post: {e}")
                continue

        # Итоговый отчет
        try:
            report = self.parser.get_last_scan_report()
            from config import BOT_TOKEN, LEADS_GROUP_CHAT_ID, THREAD_ID_LOGS
            bot = _bot_for_send() or Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            await bot.send_message(LEADS_GROUP_CHAT_ID, report, message_thread_id=THREAD_ID_LOGS)
        except Exception:
            pass

        logger.info(f"🏹 Охота завершена. Найдено лидов: {len(all_posts)}, отправлено карточек: {cards_sent}")

    async def _send_lead_card_to_group(self, lead, lead_id, profile_url, post_url, card_header):
        from config import BOT_TOKEN, LEADS_GROUP_CHAT_ID, THREAD_ID_HOT_LEADS
        if not BOT_TOKEN or not LEADS_GROUP_CHAT_ID: return False

        text = self._format_lead_card(lead, profile_url, card_header)
        buttons = [
            [InlineKeyboardButton(text="🔗 Пост", url=post_url[:500])],
            [InlineKeyboardButton(text="🛠 Ответить", callback_data=f"lead_expert_reply_{lead_id}"),
             InlineKeyboardButton(text="🤝 Взять", callback_data=f"lead_take_work_{lead_id}")]
        ]
        if profile_url and profile_url.startswith("http"):
            buttons[0].append(InlineKeyboardButton(text="👤 Профиль", url=profile_url[:500]))

        try:
            bot = _bot_for_send() or Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            await bot.send_message(LEADS_GROUP_CHAT_ID, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), message_thread_id=THREAD_ID_HOT_LEADS)
            return True
        except Exception as e:
            logger.error(f"Error sending card: {e}")
            return False

    async def _send_hot_lead_to_admin(self, lead):
        from config import BOT_TOKEN, ADMIN_ID
        if not BOT_TOKEN or not ADMIN_ID: return
        text = f"🚨 <b>ГОРЯЧИЙ ЛИД</b>\n\n{lead.get('content')[:500]}\n\n🔗 {lead.get('url')}"
        try:
            bot = _bot_for_send() or Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            await bot.send_message(ADMIN_ID, text)
        except Exception:
            pass

    async def _send_raw_leads_file_to_group(self, all_posts):
        pass
