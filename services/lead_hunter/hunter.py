import io
import logging
import os
from datetime import datetime
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton

from .discovery import Discovery
from .analyzer import LeadAnalyzer
from .outreach import Outreach
from services.scout_parser import scout_parser
from hunter_standalone import HunterDatabase, LeadHunter as StandaloneLeadHunter

logger = logging.getLogger(__name__)


def _bot_for_send():
    """Единый источник: бот из main.py через utils.bot_config.get_main_bot(). Fallback Bot(token=...) только при запуске hunt вне main (например run_hunt_once) — иначе возможен TelegramConflictError."""
    try:
        from utils.bot_config import get_main_bot
        return get_main_bot()
    except Exception:
        return None

POTENTIAL_LEADS_DB = os.path.join(os.path.dirname(__file__), "..", "..", "database", "potential_leads.db")


class LeadHunter:
    """Автономный поиск и привлечение клиентов (Lead Hunter)"""

    def __init__(self):
        self.discovery = Discovery()
        self.analyzer = LeadAnalyzer()
        self.outreach = Outreach()
        self.parser = scout_parser  # общий экземпляр: отчёт последнего скана доступен и для /spy_report

    def match_portfolio_cases(self, geo: str, intent: str) -> list:
        """Заглушка для подбора похожих кейсов из портфолио TERION (будет реализовано позже)."""
        logger.debug(f"Matching portfolio for {geo} / {intent}")
        return []

    def _format_lead_card(
        self,
        lead: dict,
        profile_url: str = "",
        card_header: str = "",
        anton_recommendation: str = "",
    ) -> str:
        """Форматирует карточку лида. Умный Охотник v2.0: при наличии recommendation — формат с вердиктом и болью."""
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

    async def _generate_sales_reply(
        self,
        post_text: str,
        pain_stage: str,
        zhk_name: str,
        intent: str,
        context_summary: str,
    ) -> str:
        """
        Генерирует через Yandex GPT проект сообщения для ответа автору поста.
        Учитывает стадию боли (ST-1…ST-4) и название ЖК.
        Возвращает готовый текст ответа — максимально живой, 2–4 предложения.
        """
        # ── Загружаем Базу Знаний TERION ─────────────────────────────────────
        kb_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "knowledge_base", "sales", "hunter_manual.md"
        )
        knowledge_base = ""
        try:
            kb_abs = os.path.abspath(kb_path)
            if os.path.exists(kb_abs):
                with open(kb_abs, "r", encoding="utf-8") as f:
                    knowledge_base = f.read().strip()
        except Exception:
            pass

        # ── Тактика ответа по стадии боли ────────────────────────────────────
        pain_scripts = {
            "ST-4": (
                "Человек получил предписание МЖИ, к нему пришла инспекция или "
                "заблокирована сделка. Напиши СРОЧНЫЙ, участливый ответ: "
                "покажи, что понимаешь критичность ситуации, предложи бесплатную "
                "срочную консультацию. Подчеркни, что TERION специализируется "
                "именно на таких случаях и знает, как быстро закрыть предписание."
            ),
            "ST-3": (
                "Человек активно делает ремонт или уже сделал без проекта и боится "
                "последствий. Напиши экспертный дружелюбный ответ: "
                "предложи зафиксировать сделанное до прихода инспекции, "
                "расскажи о рисках и предложи помощь TERION в согласовании."
            ),
            "ST-2": (
                "Человек планирует перепланировку или ремонт. "
                "Напиши полезный ответ с конкретным советом по первому шагу, "
                "объясни, почему важно начать с проекта, "
                "предложи бесплатную консультацию TERION."
            ),
            "ST-1": (
                "Человек просто интересуется темой перепланировок. "
                "Напиши краткий образовательный ответ с одним полезным фактом. "
                "Мягко упомяни, что TERION готов помочь, если понадобится."
            ),
        }
        script_hint = pain_scripts.get(pain_stage, pain_scripts["ST-2"])
        zhk_hint = f"ЖК {zhk_name.title()}" if zhk_name else "чат жильцов"

        kb_section = f"\n\n---\nБАЗА ЗНАНИЙ TERION:\n{knowledge_base}" if knowledge_base else ""

        system_prompt = (
            "Ты — Агент-Продавец компании TERION по согласованию перепланировок в Москве. "
            "Роль: Друг-эксперт. Сначала помогаешь решить проблему, потом предлагаешь услугу. "
            "Пишешь живой ответ в публичный Telegram-чат жильцов. "
            "Правила: не начинай с 'Здравствуйте', без маркетинговых клише, "
            "пиши как живой человек-эксперт, 2–4 предложения максимум. "
            "В конце всегда добавь: @terion_expert — для связи. "
            "НЕ включай скобки, пометки вроде [имя] или [ЖК]."
            f"{kb_section}"
        )
        user_prompt = (
            f"Чат: {zhk_hint}\n"
            f"Стадия боли клиента: {pain_stage}\n"
            f"Сообщение клиента: \"{(post_text or '')[:400]}\"\n"
            f"Интент: {intent}\n"
            f"Контекст: {context_summary}\n\n"
            f"Тактика ответа: {script_hint}\n\n"
            "Напиши только готовый текст ответа, без объяснений и заголовков."
        )

        try:
            from utils.yandex_gpt import generate
            reply = await generate(
                system_prompt=system_prompt,
                user_message=user_prompt,
                max_tokens=300,
            )
            result = (reply or "").strip()
            if result:
                return result
            raise ValueError("Yandex GPT вернул пустой ответ")
        except Exception as e:
            logger.debug("Ошибка генерации ответа продавца: %s", e)
            fallbacks = {
                "ST-4": (
                    "Ситуация серьёзная — если МЖИ уже выдало предписание, "
                    "важно действовать быстро. TERION специализируется именно на таких случаях: "
                    "помогаем закрыть предписание и согласовать в короткие сроки. "
                    "Напишите — разберём бесплатно: @terion_expert"
                ),
                "ST-3": (
                    "Советую зафиксировать всё, что уже сделано, до прихода инспекции. "
                    "TERION поможет оформить проект и согласовать — в том числе задним числом. "
                    "Пишите: @terion_expert"
                ),
                "ST-2": (
                    "Первый шаг — понять, затрагивает ли ваша идея несущие конструкции "
                    "и мокрые зоны. Если да — без проекта не обойтись. "
                    "Консультация бесплатно: @terion_expert"
                ),
                "ST-1": (
                    "Перепланировку можно согласовать заранее или узаконить после — "
                    "всё зависит от типа изменений. "
                    "Если нужна конкретика — @terion_expert"
                ),
            }
            return fallbacks.get(pain_stage, fallbacks["ST-2"])

    async def _analyze_intent(self, text: str) -> dict:
        """Анализ намерения через Yandex GPT агент — возвращает структуру:
        {is_lead: bool, intent: str, hotness: int(1-5), context_summary: str, recommendation: str, pain_level: int}
        """
        import os
        if not text or not (text or "").strip():
            return {"is_lead": False, "intent": "", "hotness": 0, "context_summary": "", "recommendation": "", "pain_level": 0}

        use_agent = os.getenv("USE_YANDEX_AGENT", "true").lower() == "true"
        # Allow explicit folder env var name from .env: YANDEX_FOLDER_ID
        if os.getenv("YANDEX_FOLDER_ID"):
            os.environ.setdefault("FOLDER_ID", os.getenv("YANDEX_FOLDER_ID"))
        # Ensure API key env is present for client (utils/yandex_gpt reads env on import)
        if os.getenv("YANDEX_API_KEY"):
            os.environ.setdefault("YANDEX_API_KEY", os.getenv("YANDEX_API_KEY"))

        system_prompt = (
            "Ты — ведущий эксперт компании TERION. Твоя цель — найти клиентов, которым нужно согласование перепланировки или проект БТИ в Москве. "
            "Игнорируй предложения услуг от конкурентов. Выделяй только тех, кто описывает свою проблему или ищет специалиста. "
            "Отвечай ТОЛЬКО JSON-объектом с полями: is_lead (true/false), intent (короткая строка), "
            "hotness (число 1-5), context_summary (краткое резюме 1-3 предложения), recommendation (короткая рекомендация), pain_level (1-5)."
        )
        user_prompt = f"Проанализируй сообщение и верни JSON:\n\n\"{text}\""

        if not use_agent:
            # Fallback: простая эвристика / mock
            import re
            text_l = (text or "").lower()
            if any(k in text_l for k in ["перепланиров", "снос", "объединен", "мокр", "бти", "узакон"]):
                return {"is_lead": True, "intent": "Запрос по перепланировке/БТИ", "hotness": 3, "context_summary": text[:200], "recommendation": "", "pain_level": 3}
            return {"is_lead": False, "intent": "", "hotness": 0, "context_summary": "", "recommendation": "", "pain_level": 0}

        # Use Yandex agent
        try:
            from utils.yandex_gpt import generate
            resp = await generate(system_prompt=system_prompt, user_message=user_prompt, max_tokens=400)
            import json, re
            m = re.search(r'\{[\s\S]*\}', resp or "")
            if not m:
                logger.debug("Yandex returned no JSON: %s", resp)
                return {"is_lead": False, "intent": "", "hotness": 0, "context_summary": "", "recommendation": "", "pain_level": 0}
            out = json.loads(m.group(0))
            out.setdefault("is_lead", bool(out.get("is_lead")))
            out.setdefault("intent", out.get("intent", "") or "")
            try:
                out["hotness"] = int(out.get("hotness", 0))
            except Exception:
                out["hotness"] = 0
            out.setdefault("context_summary", out.get("context_summary", "") or "")
            out.setdefault("recommendation", out.get("recommendation", "") or "")
            try:
                out["pain_level"] = int(out.get("pain_level", min(out.get("hotness", 0), 5)))
            except Exception:
                out["pain_level"] = min(out.get("hotness", 0), 5)
            return out
        except Exception as e:
            logger.exception("Ошибка Yandex intent анализатора: %s", e)
            return {"is_lead": False, "intent": "", "hotness": 0, "context_summary": "", "recommendation": "", "pain_level": 0}

    async def _send_lead_card_to_group(
        self,
        lead: dict,
        lead_id: int,
        profile_url: str,
        post_url: str,
        card_header: str = "",
        anton_recommendation: str = "",
    ) -> bool:
        """Отправляет карточку лида в рабочую группу (топик «Горячие лиды») отдельным сообщением с кнопками."""
        from config import BOT_TOKEN, LEADS_GROUP_CHAT_ID, THREAD_ID_HOT_LEADS
        if not BOT_TOKEN or not LEADS_GROUP_CHAT_ID:
            logger.warning("⚠️ BOT_TOKEN или LEADS_GROUP_CHAT_ID не заданы — карточка в группу не отправлена")
            return False
        text = self._format_lead_card(lead, profile_url, card_header, anton_recommendation)
        buttons = []
        if profile_url and profile_url.startswith("http"):
            buttons.append(InlineKeyboardButton(text="👤 Профиль", url=profile_url))
        buttons.append(InlineKeyboardButton(text="🔗 Пост", url=post_url[:500]))
        buttons.append(InlineKeyboardButton(text="🛠 Ответить экспертно", callback_data=f"lead_expert_reply_{lead_id}"))
        buttons.append(InlineKeyboardButton(text="🛠 Взять в работу", callback_data=f"lead_take_work_{lead_id}"))
        keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons])
        try:
            bot = _bot_for_send()
            if bot is None:
                bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            try:
                thread_id = THREAD_ID_HOT_LEADS if THREAD_ID_HOT_LEADS else None
                await bot.send_message(
                    LEADS_GROUP_CHAT_ID,
                    text,
                    reply_markup=keyboard,
                    message_thread_id=thread_id,
                )
                return True
            finally:
                if _bot_for_send() is None and getattr(bot, "session", None):
                    try:
                        await bot.session.close()
                    except Exception:
                        pass
        except Exception as e:
            logger.error("❌ Не удалось отправить карточку лида в группу: %s", e)
            return False

    async def _get_anton_recommendation(self, post_text: str, db) -> str:
        """Подсказка для карточки лида: МЖИ/предписание → срочный выезд; ключи/дизайн → проверка проекта (sales_templates)."""
        if not post_text:
            return ""
        t = post_text.lower()
        if "мжи" in t or "предписание" in t:
            body = await db.get_sales_template("mji_prescription")
            return body or "Срочный выезд и аудит документов"
        if "ключ" in t or "дизайн" in t:
            body = await db.get_sales_template("keys_design")
            return body or "Проверка проекта на реализуемость"
        return ""

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
            bot = _bot_for_send()
            if bot is None:
                bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            try:
                await bot.send_document(
                    LEADS_GROUP_CHAT_ID,
                    doc,
                    caption=f"📎 Список лидов по скану ({len(all_posts)} постов с ключевыми словами). Источник, превью текста, ссылка.",
                    message_thread_id=THREAD_ID_LOGS,
                )
                logger.info("📎 Файл со списком лидов отправлен в группу (топик Логи)")
                return True
            finally:
                if _bot_for_send() is None and getattr(bot, "session", None):
                    try:
                        await bot.session.close()
                    except Exception:
                        pass
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
            bot = _bot_for_send()
            if bot is None:
                bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            try:
                await bot.send_message(ADMIN_ID, text)
            finally:
                if _bot_for_send() is None and getattr(bot, "session", None):
                    try:
                        await bot.session.close()
                    except Exception:
                        pass
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
            bot = _bot_for_send()
            if bot is None:
                bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            try:
                await bot.send_message(ADMIN_ID, text)
            finally:
                if _bot_for_send() is None and getattr(bot, "session", None):
                    try:
                        await bot.session.close()
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"❌ Не удалось отправить горячий лид админу: {e}")

    @staticmethod
    def _is_business_hours_msk() -> bool:
        """True если текущее время 09:00–20:00 по МСК (UTC+3)."""
        from datetime import timezone, timedelta
        msk = timezone(timedelta(hours=3))
        hour = datetime.now(msk).hour
        return 9 <= hour < 20

    async def hunt(self):
        """Полный цикл: поиск → анализ → привлечение + проверка через AI Жюля и пересылка горячих лидов."""
        logger.info("🏹 LeadHunter: начало охоты за лидами...")

        # Принудительная очистка кеша парсера перед началом скана:
        # сбрасываем предыдущие отчёты и список чатов, чтобы не опираться на старые смещения/сканы.
        try:
            self.parser.last_scan_report = []
            self.parser.last_scan_chats_list = []
            self.parser.last_scan_at = datetime.now()
            logger.info("🔄 ScoutParser cache cleared before hunt (forced).")
        except Exception:
            pass

        from database import db as main_db
        tg_posts = await self.parser.parse_telegram(db=main_db)
        vk_posts = await self.parser.parse_vk()
        all_posts = tg_posts + vk_posts

        # Если лидов не найдено, пробуем найти новые источники через Discovery
        if not all_posts:
            logger.info("🔎 Лидов не найдено. Запуск Discovery для поиска новых источников...")
            new_sources = await self.discovery.find_new_sources()
            for source in new_sources:
                try:
                    await main_db.add_target_resource(
                        resource_type="telegram",
                        link=source["link"],
                        title=source["title"],
                        notes="Найден через LeadHunter Discovery",
                        status="pending",
                        participants_count=source.get("participants_count")
                    )
                except Exception as e:
                    logger.debug(f"Ошибка добавления ресурса из Discovery: {e}")

        # Сброс старого кеша: игнорируем первые N сообщений (старые) — по умолчанию 0
        try:
            skip_count = int(os.getenv("SPY_SKIP_OLD_MESSAGES", "0"))
        except Exception:
            skip_count = 0
        
        if skip_count > 0 and len(all_posts) > skip_count:
            remaining = all_posts[skip_count:]
        else:
            remaining = all_posts

        # Переключиться на приоритетные чаты (ЖК Династия, Зиларт) — перемещаем их в начало
        preferred_names = [n.lower() for n in os.getenv("SPY_PREFERRED_CHATS", "Династия,Зиларт").split(",") if n.strip()]
        def is_preferred(p):
            name = (getattr(p, "source_name", "") or "").lower()
            return any(pref in name for pref in preferred_names)
        preferred = [p for p in remaining if is_preferred(p)]
        others = [p for p in remaining if not is_preferred(p)]
        all_posts = preferred + others

        tg_ok = [r for r in (self.parser.last_scan_report or []) if r.get("type") == "telegram" and r.get("status") == "ok"]
        vk_ok = [r for r in (self.parser.last_scan_report or []) if r.get("type") == "vk" and r.get("status") == "ok"]
        logger.info(
            "🔍 ScoutParser: просканировано TG каналов=%s, VK групп=%s, постов с ключевыми словами=%s",
            len(tg_ok), len(vk_ok), len(all_posts)
        )

        from hunter_standalone.database import HunterDatabase as LocalHunterDatabase
        # Анти-дубль: в рамках одного запуска не обрабатываем один и тот же post_id дважды
        _seen_post_keys: set[str] = set()
        _business_hours = self._is_business_hours_msk()
        logger.info("🕐 Бизнес-часы МСК: %s", "да (09:00–20:00)" if _business_hours else "нет — горячие лиды не отправляются")

        for post in all_posts:
            _post_key = f"{getattr(post, 'source_type', '')}:{getattr(post, 'source_id', '')}:{getattr(post, 'post_id', '')}"
            if _post_key in _seen_post_keys:
                logger.debug("⏭️ Анти-дубль: post %s уже обработан в этом цикле", _post_key)
                continue
            _seen_post_keys.add(_post_key)

            # Быстрая оценка через LeadAnalyzer (существующая ранняя логика) — ТЕПЕРЬ ВОЗВРАЩАЕТ DICT
            analysis_data = await self.analyzer.analyze_post(post.text)
            score = analysis_data.get("priority_score", 0) / 10.0 # Приводим к 0.0 - 1.0 для совместимости
            pain_stage = analysis_data.get("pain_stage", "ST-1")

            # Глубокий анализ намерения через Yandex GPT агент (новая логика)
            try:
                analysis = await self._analyze_intent(post.text)
            except Exception as e:
                logger.debug("🔎 Анализ намерения не удался: %s", e)
                analysis = {"is_lead": False, "intent": "", "hotness": 0, "context_summary": ""}

            # Если модель пометила как лид — сохраняем в локальную HunterDatabase, чтобы избежать дублей
            if analysis.get("is_lead"):
                try:
                    db_path = os.path.abspath(POTENTIAL_LEADS_DB)
                    hd = LocalHunterDatabase(db_path)
                    await hd.connect()
                    lead_data = {
                        "url": getattr(post, "url", "") or f"{getattr(post, 'source_type', '')}/{getattr(post, 'source_id', '')}/{getattr(post, 'post_id', '')}",
                        "content": (getattr(post, "text", "") or "")[:2000],
                        "intent": analysis.get("intent", "") or "",
                        "hotness": analysis.get("hotness", 3),
                        "geo": analysis.get("geo", "Не указано"),
                        "context_summary": analysis.get("context_summary", "") or "",
                        "pain_stage": pain_stage,
                        "priority_score": analysis_data.get("priority_score", 0),
                    }
                    saved = await hd.save_lead(lead_data)
                    try:
                        if hd.conn:
                            await hd.conn.close()
                    except Exception:
                        pass
                except Exception as e:
                    logger.debug("Ошибка сохранения в HunterDatabase: %s", e)
                    saved = False
                # Если новый лид (сохранён) — немедленно уведомляем Юлию (Anton -> Julia)
                if saved:
                    try:
                        from config import JULIA_USER_ID, BOT_TOKEN
                        from services.lead_hunter.analyzer import _detect_priority_zhk_hot

                        # ── Профиль автора ───────────────────────────────────
                        author_id = getattr(post, "author_id", None)
                        author_name = getattr(post, "author_name", None)
                        src_type = getattr(post, "source_type", "telegram")
                        if src_type == "vk" and author_id:
                            author_link = f"https://vk.com/id{author_id}"
                        elif author_id:
                            author_link = f"tg://user?id={author_id}"
                        else:
                            author_link = None

                        # ── Приоритетный ЖК ──────────────────────────────────
                        is_zhk_hot, zhk_name = _detect_priority_zhk_hot(post.text or "")
                        zhk_name = zhk_name or analysis_data.get("zhk_name") or analysis.get("zhk_name") or ""

                        # ── Стадия боли ───────────────────────────────────────
                        pain_stage = analysis_data.get("pain_stage") or ""
                        pain_label = {
                            "ST-4": "⛔ Критично",
                            "ST-3": "🔴 Активная боль",
                            "ST-2": "🟡 Планирование",
                            "ST-1": "🟢 Интерес",
                        }.get(pain_stage, "")

                        # ── Генерируем проект ответа через Yandex GPT ─────────
                        sales_draft = ""
                        try:
                            sales_draft = await self._generate_sales_reply(
                                post_text=post.text or "",
                                pain_stage=pain_stage or "ST-2",
                                zhk_name=zhk_name,
                                intent=analysis.get("intent", ""),
                                context_summary=analysis.get("context_summary", ""),
                            )
                        except Exception as draft_err:
                            logger.debug("Не удалось сгенерировать проект ответа: %s", draft_err)

                        # ── Строим карточку лида ──────────────────────────────
                        if is_zhk_hot or zhk_name:
                            header = f"🚨 <b>ГОРЯЧИЙ ЛИД — ЖК {zhk_name.title()}</b>"
                        else:
                            header = "🔥 <b>Новый лид</b>"

                        lines = [
                            header,
                            "",
                            f"🎯 {analysis.get('intent', '—')}",
                            f"📍 ЖК/Гео: {analysis.get('geo', getattr(post, 'source_name', '—'))}",
                            f"📝 Суть: {analysis.get('context_summary', '—')}",
                        ]
                        if pain_label:
                            lines.append(f"🩺 Стадия: {pain_label} ({pain_stage})")
                        if author_link:
                            if src_type == "telegram":
                                lines.append(f"👤 Автор: <code>{author_link}</code>")
                            else:
                                lines.append(f'👤 Автор: <a href="{author_link}">{author_name or "профиль"}</a>')
                        elif author_name:
                            lines.append(f"👤 Автор: @{author_name}")
                        lines.append(f"🔗 Пост: {lead_data.get('url', '—')}")

                        # ── Блок с проектом ответа (жмёшь → копируешь) ───────
                        if sales_draft:
                            lines += [
                                "",
                                "─" * 22,
                                "✍️ <b>Проект ответа (Антон):</b>",
                                f"<code>{sales_draft}</code>",
                                "─" * 22,
                            ]

                        card_text = "\n".join(lines)

                        # ── Кнопки: Написать автору + Открыть пост ────────────
                        buttons_row = []
                        if author_link:
                            buttons_row.append(
                                InlineKeyboardButton(
                                    text="👤 Написать автору",
                                    url=author_link,
                                )
                            )
                        post_url = lead_data.get("url") or ""
                        if post_url and post_url.startswith("http"):
                            buttons_row.append(
                                InlineKeyboardButton(text="🔗 Открыть пост", url=post_url[:500])
                            )
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons_row]) if buttons_row else None

                        bot = _bot_for_send()
                        if bot is None:
                            bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
                        try:
                            await bot.send_message(
                                int(JULIA_USER_ID),
                                card_text,
                                parse_mode="HTML",
                                disable_web_page_preview=True,
                                reply_markup=keyboard,
                            )
                        finally:
                            if _bot_for_send() is None and getattr(bot, "session", None):
                                try:
                                    await bot.session.close()
                                except Exception:
                                    pass
                    except Exception as e:
                        logger.debug("Не удалось отправить уведомление Юлии: %s", e)

            # Существующая логика исходящих сообщений (контент-бот / outreach)
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
                    if lead.get("hotness", 0) < 3:
                        continue
                    if lead.get("hotness", 0) > 4:
                        logger.info(f"🔥 Горячий лид (Жюль, hotness={lead.get('hotness')}) → пересылка админу")
                        await self._send_hot_lead_to_admin(lead)
                    # Сопоставляем с постом для author_id / username
                    post = find_post_by_url(lead.get("url", ""))
                    author_id = getattr(post, "author_id", None) if post else None
                    author_name = getattr(post, "author_name", None) if post else None
                    source_name = getattr(post, "source_name", "") if post else "—"
                    source_type = getattr(post, "source_type", "telegram") if post else "telegram"
                    post_text = getattr(post, "text", "") if post else ""
                    # Заголовок карточки: приоритетный ЖК (Высотка) или geo_tag / title (Управление географией)
                    card_header = source_name
                    res = None
                    if post:
                        source_link = getattr(post, "source_link", None)
                        if source_link:
                            try:
                                from database import db as main_db
                                res = await main_db.get_target_resource_by_link(source_link)
                                if res:
                                    is_high = res.get("is_high_priority") or 0
                                    name_part = (res.get("geo_tag") or "").strip() or res.get("title") or self.parser.extract_geo_header(post_text, source_name) or source_name
                                    if is_high:
                                        card_header = f"🏙 ПРИОРИТЕТНЫЙ ЖК (Высотка)\n{name_part}" if name_part else "🏙 ПРИОРИТЕТНЫЙ ЖК (Высотка)"
                                    else:
                                        card_header = name_part
                                else:
                                    card_header = self.parser.extract_geo_header(post_text, source_name)
                            except Exception:
                                card_header = self.parser.extract_geo_header(post_text, source_name)
                        else:
                            card_header = self.parser.extract_geo_header(post_text, source_name)
                    # Лидогенерация: если нет username — вытягиваем ID для прямой ссылки tg://user?id=...
                    profile_url = ""
                    if author_id is not None and source_type == "vk":
                        aid = int(author_id) if isinstance(author_id, (int, str)) and str(author_id).lstrip("-").isdigit() else 0
                        if aid > 0:
                            profile_url = f"https://vk.com/id{aid}"
                    elif author_id is not None and source_type == "telegram":
                        profile_url = f"tg://user?id={author_id}"
                    post_url = lead.get("url", "") or ""
                    try:
                        from database import db as main_db
                        lead_id = await main_db.add_spy_lead(
                            source_type=source_type,
                            source_name=source_name,
                            url=post_url,
                            text=(lead.get("content") or lead.get("intent") or "")[:2000],
                            author_id=str(author_id) if author_id else None,
                            username=author_name,
                            profile_url=profile_url or None,
                            pain_stage=lead.get("pain_stage"),
                            priority_score=lead.get("priority_score"),
                        )
                    except Exception as e:
                        logger.warning("Не удалось сохранить spy_lead: %s", e)
                        lead_id = 0
                    if not lead_id:
                        lead_id = 0
                    # Уведомление в личку админу при каждом лиде (если включено в пульте)
                    try:
                        from database import db as main_db
                        notify_enabled = await main_db.get_setting("spy_notify_enabled", "1")
                        if notify_enabled == "1":
                            await self._send_lead_notify_to_admin(lead, source_name, profile_url or post_url)
                    except Exception:
                        pass
                    # Рекомендация Антона (Ассистент Продаж): по тексту подбираем скрипт из sales_templates
                    anton_recommendation = ""
                    try:
                        from database import db as main_db
                        anton_recommendation = await self._get_anton_recommendation(post_text, main_db)
                    except Exception:
                        pass
                    # Карточка лида в рабочую группу — только ST-4 в рабочее время МСК.
                    # Остальные стадии не шумят в «Горячие лиды» вне расписания.
                    _lead_stage = lead.get("pain_stage") or ""
                    _is_hot = _lead_stage == "ST-4" or lead.get("hotness", 0) >= 4
                    if cards_sent < MAX_CARDS_PER_RUN and (_is_hot and _business_hours or not _is_hot):
                        if await self._send_lead_card_to_group(lead, lead_id, profile_url, post_url, card_header, anton_recommendation):
                            cards_sent += 1
                    elif _is_hot and not _business_hours:
                        logger.info(
                            "🌙 Горячий лид ST-4 найден вне рабочего времени МСК — "
                            "карточка в группу отложена до 09:00. URL: %s", post_url
                        )
                if cards_sent:
                    logger.info("📋 В рабочую группу отправлено карточек лидов: %s", cards_sent)
                # Дублирование в рабочую группу: краткий отчёт о сохранённых лидах
                if hot_leads:
                    from config import BOT_TOKEN, LEADS_GROUP_CHAT_ID, THREAD_ID_LOGS
                    if BOT_TOKEN and LEADS_GROUP_CHAT_ID:
                        try:
                            bot = _bot_for_send()
                            if bot is None:
                                bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
                            try:
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
                            finally:
                                if _bot_for_send() is None and getattr(bot, "session", None):
                                    try:
                                        await bot.session.close()
                                    except Exception:
                                        pass
                        except Exception as e:
                            logger.warning("Не удалось отправить сводку лидов в группу: %s", e)
            except Exception as e:
                logger.error(f"❌ Ошибка hunter_standalone (AI Жюля): {e}")

        # Отчёт в рабочую группу: где был шпион, в какие группы/каналы удалось попасть
        try:
            from config import BOT_TOKEN, LEADS_GROUP_CHAT_ID, THREAD_ID_LOGS
            report = self.parser.get_last_scan_report()
            if BOT_TOKEN and LEADS_GROUP_CHAT_ID and report and "Отчёта ещё нет" not in report:
                bot = _bot_for_send()
                if bot is None:
                    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
                try:
                    await bot.send_message(
                        LEADS_GROUP_CHAT_ID,
                        report,
                        message_thread_id=THREAD_ID_LOGS,
                    )
                finally:
                    if _bot_for_send() is None and getattr(bot, "session", None):
                        try:
                            await bot.session.close()
                        except Exception:
                            pass
        except Exception as e:
            logger.warning("Не удалось отправить отчёт шпиона в группу: %s", e)

        # Файл со списком всех лидов (источник, превью текста, ссылка) — в тот же топик «Логи»
        if all_posts:
            await self._send_raw_leads_file_to_group(all_posts)

        logger.info(f"🏹 LeadHunter: охота завершена. Обработано {len(all_posts)} постов.")
