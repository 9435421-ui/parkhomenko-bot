import io
import logging
import os
from datetime import datetime
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton

from services.lead_hunter.discovery import Discovery
# from .outreach import Outreach  # Файл outreach.py не существует, импорт удален
from services.scout_parser import scout_parser
from services.lead_hunter import HunterDatabase, LeadHunter as StandaloneLeadHunter

# Создаем отдельный логгер для модуля шпионажа
logger = logging.getLogger(__name__)
vk_spy_logger = logging.getLogger("VK_SPY")

# =============================================================================
# СТОП-СЛОВА (Pre-filter): Жесткая фильтрация до отправки в AI
# =============================================================================
# Если текст содержит любое из этих слов, пост игнорируется без траты токенов
# =============================================================================
# Если текст содержит любое из этих слов, пост игнорируется без траты токенов
# =============================================================================
# Если текст содержит любое из этих слов, пост игнорируется без траты токенов
# =============================================================================
# Если текст содержит любое из этих слов, пост игнорируется без траты токенов
# =============================================================================
# Если текст содержит любое из этих слов, пост игнорируется без траты токенов
# =============================================================================
# Если текст содержит любое из этих слов, пост игнорируется без траты токенов
# =============================================================================
# Если текст содержит любое из этих слов, пост игнорируется без траты токенов
# =============================================================================
# Если текст содержит любое из этих слов, пост игнорируется без траты токенов
# =============================================================================
# Если текст содержит любое из этих слов, пост игнорируется без траты токенов
# =============================================================================
# Если текст содержит любое из этих слов, пост игнорируется без траты токенов
# =============================================================================

# Категория «Образование и Наука»
STOP_WORDS_EDUCATION = [
    "студент", "кафедра", "доцент", "преподаватель", "лекция", "учебный",
    "диссертация", "БГИТУ", "вуз", "колледж", "аспирант", "экзамен",
    "занятие", "наука", "университет", "институт", "академия"
]

# Категория «Экспертный спам»
STOP_WORDS_EXPERT_SPAM = [
    "подписывайтесь", "наш канал", "заказать услугу", "статья",
    "рассказываем в видео", "чек-лист", "бесплатный гайд",
    "обучение перепланировкам", "курс", "вебинар", "мастер-класс",
    "юридическая справка", "советы юриста", "обзор закона"
]

# Категория «Общий шум»
STOP_WORDS_GENERAL = [
    "вакансия", "требуется", "сдам квартиру", "продам машину",
    "поздравляем с днем", "памятная дата", "юбилей", "торжество",
    "новости жк", "отключение воды", "ремонт дороги"
]

# Объединенный список всех стоп-слов
STOP_WORDS_ALL = STOP_WORDS_EDUCATION + STOP_WORDS_EXPERT_SPAM + STOP_WORDS_GENERAL


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
        # self.outreach = Outreach()  # Файл outreach.py не существует, закомментировано
        self.parser = scout_parser  # общий экземпляр: отчёт последнего скана доступен и для /spy_report
        self._db = None  # Кэш для глобального объекта БД
    
    async def _ensure_db_connected(self):
        """Убедиться, что БД подключена. Возвращает объект БД."""
        from database import db as main_db
        if main_db.conn is None:
            logger.info("🔌 БД не подключена, выполняю подключение...")
            await main_db.connect()
        return main_db

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
        """Форматирует карточку лида для Telegram (HTML). 
        
        Формат: Статус (эмодзи), Источник, Контент (300 символов), User handle, Score.
        """
        recommendation = (lead.get("recommendation") or anton_recommendation or "").strip()
        pain_level = lead.get("pain_level") or min(lead.get("hotness", 3), 5)
        pain_stage = lead.get("pain_stage", "ST-1")
        
        if pain_stage == "ST-4" or (recommendation and pain_level >= 4):
            return self._format_lead_card_v2(lead, profile_url, card_header, recommendation, pain_level)
        
        # ── ОБРЕЗКА КОНТЕНТА ДО 300 СИМВОЛОВ ────────────────────────────────────────
        content = (lead.get("content") or lead.get("text") or lead.get("intent") or "").strip()
        if len(content) > 300:
            content = content[:300] + "…"
        
        # ── ЭМОДЗИ СТАТУСА ПО СТАДИИ БОЛИ ───────────────────────────────────────────
        pain_emoji = {
            "ST-1": "💡",
            "ST-2": "📋",
            "ST-3": "🔥",
            "ST-4": "🚨"
        }
        status_emoji = pain_emoji.get(pain_stage, "💡")
        
        # ── USER HANDLE ─────────────────────────────────────────────────────────────
        user_handle = ""
        author_name = lead.get("author_name") or lead.get("username") or ""
        author_id = lead.get("author_id") or lead.get("user_id") or ""
        
        if author_name:
            user_handle = f"@{author_name}" if not author_name.startswith("@") else author_name
        elif author_id:
            user_handle = f"ID: {author_id}"
        else:
            user_handle = "—"
        
        # ── ПРИОРИТЕТ И SCORE ───────────────────────────────────────────────────────
        priority_score = lead.get("priority_score", 0)
        priority_bar = "█" * min(priority_score, 10) + "░" * (10 - min(priority_score, 10))
        
        # ── ИСТОЧНИК ───────────────────────────────────────────────────────────────
        source = card_header or lead.get("source_name") or lead.get("source") or "Неизвестный источник"
        
        # ── ФОРМИРОВАНИЕ КАРТОЧКИ ───────────────────────────────────────────────────
        lines = [
            f"{status_emoji} <b>Статус:</b> {pain_stage}",
            f"📊 <b>Источник:</b> {source}",
            "",
            f"📄 <b>Содержание:</b>\n{content}",
            "",
            f"👤 <b>Пользователь:</b> {user_handle}",
            f"⭐ <b>Приоритет:</b> {priority_score}/10",
            f"📊 {priority_bar}",
        ]
        
        if anton_recommendation:
            lines.append(f"\n💡 <b>Рекомендация:</b> {anton_recommendation}")
        
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
        
        # ── ОБНОВЛЕННЫЙ ФОРМАТ: Эмодзи 🚨 для ST-4 и шкала приоритета ─────────────
        priority_score = lead.get("priority_score", 0)
        pain_stage = lead.get("pain_stage", "ST-1")
        
        # Шкала приоритета (визуальная)
        priority_bar = "█" * min(priority_score, 10) + "░" * (10 - min(priority_score, 10))
        
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
        ]
        
        # Добавляем шкалу приоритета если есть
        if priority_score > 0:
            lines.extend([
                f"⭐ Приоритет: {priority_score}/10",
                f"📊 {priority_bar}",
            ])
        
        lines.extend([
            f"<b>Вердикт:</b> {recommendation[:500]}",
            "",
            f"🔗 Пост: {lead.get('url', '')}",
        ])
        return "\n".join(lines)

    async def _generate_sales_reply(
        self,
        post_text: str,
        pain_stage: str,
        zhk_name: str,
        intent: str,
        context_summary: str,
        platform: str = "telegram",
        is_priority_zhk: bool = False,
    ) -> str:
        """
        Генерирует через Yandex GPT проект сообщения для ответа автору поста.
        Учитывает стадию боли (ST-1…ST-4), название ЖК, платформу и приоритет ЖК.
        При ошибке Yandex GPT автоматически переключается на Router AI (fallback).
        
        Args:
            post_text: Текст поста от клиента
            pain_stage: Стадия боли (ST-1/ST-2/ST-3/ST-4)
            zhk_name: Название ЖК
            intent: Интент клиента
            context_summary: Краткое резюме контекста
            platform: Платформа ("telegram" или "vk")
            is_priority_zhk: Является ли ЖК приоритетным
        
        Returns:
            str: Готовый текст ответа (2-4 предложения)
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
        
        # Формируем информацию о приоритете и платформе для промпта
        priority_note = ""
        if is_priority_zhk:
            priority_note = "\n⚠️ ВАЖНО: Это приоритетный ЖК (Высотка) — ответ должен быть особенно внимательным и профессиональным."
        
        platform_note = ""
        if platform == "vk":
            platform_note = "\n📘 Платформа: VK (более формальный тон, можно использовать эмодзи умеренно)."
        else:
            platform_note = "\n📱 Платформа: Telegram (живой, дружелюбный тон)."

        kb_section = f"\n\n---\nБАЗА ЗНАНИЙ TERION:\n{knowledge_base}" if knowledge_base else ""

        system_prompt = (
            "Ты — Агент-Продавец компании TERION по согласованию перепланировок в Москве. "
            "Роль: Друг-эксперт. Сначала помогаешь решить проблему, потом предлагаешь услугу. "
            f"Пишешь живой ответ в публичный {platform.upper()}-чат жильцов.{priority_note}{platform_note} "
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

        # ── ПОПЫТКА 1: Основной API-ключ Яндекса ────────────────────────────────────
        try:
            from utils.yandex_gpt import generate
            reply = await generate(
                system_prompt=system_prompt,
                user_message=user_prompt,
                max_tokens=300,
            )
            result = (reply or "").strip()
            # Проверяем, что ответ не является сообщением об ошибке
            if result and not result.startswith("Ошибка") and not result.startswith("⚠️"):
                return result
            raise ValueError(f"Yandex GPT вернул ошибку или пустой ответ: {result}")
        except Exception as e:
            logger.warning(f"⚠️ Основной Yandex GPT ключ не сработал: {e}")
        
        # ── ПОПЫТКА 2: Резервный API-ключ Яндекса (если настроен) ────────────────────
        backup_key = os.getenv("YANDEX_API_KEY_BACKUP")
        if backup_key:
            try:
                logger.info("🔄 Пробую резервный API-ключ Яндекса...")
                # Временно устанавливаем резервный ключ как основной
                original_key = os.getenv("YANDEX_API_KEY")
                os.environ["YANDEX_API_KEY"] = backup_key
                try:
                    from utils.yandex_gpt import generate
                    reply = await generate(
                        system_prompt=system_prompt,
                        user_message=user_prompt,
                        max_tokens=300,
                    )
                    result = (reply or "").strip()
                    if result and not result.startswith("Ошибка") and not result.startswith("⚠️"):
                        logger.info("✅ Резервный API-ключ Яндекса успешно использован")
                        return result
                finally:
                    # Восстанавливаем оригинальный ключ
                    if original_key:
                        os.environ["YANDEX_API_KEY"] = original_key
                    else:
                        os.environ.pop("YANDEX_API_KEY", None)
            except Exception as backup_error:
                logger.warning(f"⚠️ Резервный Yandex GPT ключ также не сработал: {backup_error}")
        
        # ── ПОПЫТКА 3: Router AI fallback ──────────────────────────────────────────────
        logger.warning(f"⚠️ Все API-ключи Яндекса не сработали. Переключаюсь на Router AI fallback...")
        
        # ── FALLBACK 1: Router AI ────────────────────────────────────────────────
        try:
            from utils.router_ai import router_ai
            router_reply = await router_ai.generate_response(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=300,
                temperature=0.2,
            )
            if router_reply and router_reply.strip():
                result = router_reply.strip()
                logger.info("✅ Router AI fallback успешно сгенерировал ответ")
                return result
        except Exception as router_error:
            logger.warning(f"⚠️ Router AI fallback также не удался: {router_error}")
            
            # ── FALLBACK 2: Статические шаблоны по стадии боли ─────────────────────
            logger.debug("Использую статические шаблоны как последний fallback")
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

        # ── PRE-FILTER: Проверка стоп-слов ДО отправки в AI ────────────────────────
        text_lower = (text or "").lower()
        for stop_word in STOP_WORDS_ALL:
            if stop_word.lower() in text_lower:
                logger.debug(f"🚫 STOP_WORD обнаружен: '{stop_word}' → пост отфильтрован до отправки в AI")
                return {"is_lead": False, "intent": "", "hotness": 0, "context_summary": "", "recommendation": "", "pain_level": 0}

        use_agent = os.getenv("USE_YANDEX_AGENT", "true").lower() == "true"
        # Allow explicit folder env var name from .env: YANDEX_FOLDER_ID
        if os.getenv("YANDEX_FOLDER_ID"):
            os.environ.setdefault("FOLDER_ID", os.getenv("YANDEX_FOLDER_ID"))
        # Ensure API key env is present for client (utils/yandex_gpt reads env on import)
        if os.getenv("YANDEX_API_KEY"):
            os.environ.setdefault("YANDEX_API_KEY", os.getenv("YANDEX_API_KEY"))

        system_prompt = (
            "Классифицируй сообщение: лид ли это (живой вопрос о перепланировке/БТИ в Москве/МО) или нет.\n"
            "ЛИДЫ: «Можно ли снести стену?\", «Где узаконить?\", «Нужен проект», «Штраф за ремонт» (от первого лица).\n"
            "НЕ ЛИДЫ: статьи, советы, реклама, новости ЖК, посты от каналов.\n"
            "Стадии боли: ST-1=интерес, ST-2=уточнение, ST-3=действие, ST-4=срочно.\n"
            "JSON: {\"is_lead\": bool, \"intent\": str, \"hotness\": 1-5, \"pain_stage\": \"ST-X\"}"
        )
        user_prompt = f"Проанализируй сообщение и верни JSON:\n\n\"{text}\""

        if not use_agent:
            # Fallback: простая эвристика / mock
            import re
            text_l = (text or "").lower()
            if any(k in text_l for k in ["перепланиров", "снос", "объединен", "мокр", "бти", "узакон"]):
                return {"is_lead": True, "intent": "Запрос по перепланировке/БТИ", "hotness": 3, "context_summary": text[:200], "recommendation": "", "pain_level": 3}
            return {"is_lead": False, "intent": "", "hotness": 0, "context_summary": "", "recommendation": "", "pain_level": 0}

        # ── ПОПЫТКА 1: Основной API-ключ Яндекса ────────────────────────────────────
        try:
            from utils.yandex_gpt import generate
            resp = await generate(system_prompt=system_prompt, user_message=user_prompt, max_tokens=400)
            
            # Проверяем, что ответ не является сообщением об ошибке
            if resp and not resp.startswith("Ошибка") and not resp.startswith("⚠️"):
                import json, re
                m = re.search(r'\{[\s\S]*\}', resp or "")
                if m:
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
                else:
                    logger.debug("Yandex returned no JSON: %s", resp)
                    raise ValueError(f"Yandex GPT вернул некорректный ответ: {resp}")
            else:
                raise ValueError(f"Yandex GPT вернул ошибку: {resp}")
        except Exception as e:
            logger.warning(f"⚠️ Основной Yandex GPT ключ не сработал для анализа интента: {e}")
        
        # ── ПОПЫТКА 2: Резервный API-ключ Яндекса (если настроен) ────────────────────
        backup_key = os.getenv("YANDEX_API_KEY_BACKUP")
        if backup_key:
            try:
                logger.info("🔄 Пробую резервный API-ключ Яндекса для анализа интента...")
                # Временно устанавливаем резервный ключ как основной
                original_key = os.getenv("YANDEX_API_KEY")
                os.environ["YANDEX_API_KEY"] = backup_key
                try:
                    from utils.yandex_gpt import generate
                    resp = await generate(system_prompt=system_prompt, user_message=user_prompt, max_tokens=400)
                    result = (resp or "").strip()
                    if result and not result.startswith("Ошибка") and not result.startswith("⚠️"):
                        import json, re
                        m = re.search(r'\{[\s\S]*\}', result or "")
                        if m:
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
                            logger.info("✅ Резервный API-ключ Яндекса успешно использован для анализа интента")
                            return out
                finally:
                    # Восстанавливаем оригинальный ключ
                    if original_key:
                        os.environ["YANDEX_API_KEY"] = original_key
                    else:
                        os.environ.pop("YANDEX_API_KEY", None)
            except Exception as backup_error:
                logger.warning(f"⚠️ Резервный Yandex GPT ключ также не сработал для анализа интента: {backup_error}")
        
        # ── ПОПЫТКА 3: Router AI fallback ──────────────────────────────────────────────
        logger.warning(f"⚠️ Все API-ключи Яндекса не сработали для анализа интента. Переключаюсь на Router AI fallback...")
        try:
            # Пробуем импортировать router_ai из handlers/content.py (как в admin.py)
            try:
                from handlers.content import router_ai
                router_resp = await router_ai.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    max_tokens=400,
                )
            except ImportError:
                # Fallback: пробуем utils.router_ai
                from utils.router_ai import router_ai
                router_resp = await router_ai.generate_response(
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    max_tokens=400,
                    temperature=0.2,
                )
            
            if router_resp and router_resp.strip():
                import json, re
                m = re.search(r'\{[\s\S]*\}', router_resp or "")
                if m:
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
                    logger.info("✅ Router AI fallback успешно использован для анализа интента")
                    return out
        except Exception as router_error:
            logger.warning(f"⚠️ Router AI fallback также не удался для анализа интента: {router_error}")
        
        # ── FALLBACK: Простая эвристика как последний резерв ─────────────────────
        logger.debug("Использую простую эвристику как последний fallback для анализа интента")
        import re
        text_l = (text or "").lower()
        if any(k in text_l for k in ["перепланиров", "снос", "объединен", "мокр", "бти", "узакон"]):
            return {"is_lead": True, "intent": "Запрос по перепланировке/БТИ", "hotness": 3, "context_summary": text[:200], "recommendation": "", "pain_level": 3}
        return {"is_lead": False, "intent": "", "hotness": 0, "context_summary": "", "recommendation": "", "pain_level": 0}

    async def _send_dm_to_user(
        self,
        user_id: int,
        post_url: str,
        lead_text: str,
    ) -> bool:
        """Отправляет личное сообщение пользователю при обнаружении лида в открытом чате.
        
        Args:
            user_id: Telegram user_id пользователя
            post_url: URL поста, где был найден лид (для контекста)
            lead_text: Текст лида/вопроса пользователя
        
        Returns:
            bool: True если сообщение отправлено успешно, False если ошибка или ЛС закрыты
        """
        if not user_id or user_id <= 0:
            return False
        
        from config import BOT_TOKEN
        if not BOT_TOKEN:
            logger.warning("⚠️ BOT_TOKEN не задан — ЛС не отправлено")
            return False
        
        # Формируем сообщение от Антона
        message_text = (
            f"Здравствуйте! Я Антон, ИИ-ассистент эксперта Юлии Пархоменко (компания TERION).\n\n"
            f"Увидел ваш вопрос по поводу перепланировки:\n"
            f"«{lead_text[:200]}{'…' if len(lead_text) > 200 else ''}»\n\n"
            f"Могу помочь с согласованием перепланировки в Москве.\n"
            f"Для начала ответьте на несколько вопросов в нашем квизе:\n"
            f"https://t.me/Parkhovenko_i_kompaniya_bot?start=quiz\n\n"
            f"🔗 Ваш пост: {post_url}"
        )
        
        try:
            bot = _bot_for_send()
            if bot is None:
                bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    parse_mode=None,  # Обычный текст, без HTML
                )
                logger.info(f"✅ ЛС отправлено пользователю {user_id} (пост: {post_url[:50]}...)")
                return True
            except Exception as e:
                error_str = str(e).lower()
                # Игнорируем ошибки "bot blocked by user" или "chat not found"
                if "blocked" in error_str or "chat not found" in error_str or "user is deactivated" in error_str:
                    logger.debug(f"⏭️ ЛС недоступно для пользователя {user_id}: {e}")
                else:
                    logger.warning(f"⚠️ Ошибка отправки ЛС пользователю {user_id}: {e}")
                return False
            finally:
                if _bot_for_send() is None and getattr(bot, "session", None):
                    try:
                        await bot.session.close()
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"❌ Критическая ошибка при отправке ЛС пользователю {user_id}: {e}")
            return False

    async def _send_lead_card_for_moderation(
        self,
        lead: dict,
        lead_id: int,
        profile_url: str,
        post_url: str,
        card_header: str = "",
        post_text: str = "",
        source_type: str = "telegram",
        source_link: str = "",
        geo_tag: str = "",
        is_priority: bool = False,
        anton_recommendation: str = "",
    ) -> bool:
        """
        Отправляет карточку лида в админ-канал для модерации (Режим Модерации).
        
        Карточка содержит:
        - Платформа (TG/VK)
        - Локация (Geo Header, например: "ЖК Зиларт, корп. 5")
        - Приоритет (🔥 Высокий, если приоритетный ЖК)
        - Интерактивные кнопки: Одобрить, Редактировать, Пропустить
        """
        from config import BOT_TOKEN, LEADS_GROUP_CHAT_ID, THREAD_ID_HOT_LEADS
        if not BOT_TOKEN or not LEADS_GROUP_CHAT_ID:
            logger.warning("⚠️ BOT_TOKEN или LEADS_GROUP_CHAT_ID не заданы — карточка на модерацию не отправлена")
            return False
        
        # Формируем локацию (Geo Header)
        location = geo_tag or card_header or "Не указано"
        # Извлекаем гео-информацию из текста поста, если доступен parser
        if post_text and hasattr(self, 'parser') and self.parser and hasattr(self.parser, 'extract_geo_header'):
            try:
                extracted_location = self.parser.extract_geo_header(post_text, location)
                if extracted_location and extracted_location != location:
                    location = extracted_location
            except Exception:
                pass
        
        # Определяем платформу
        platform_emoji = "📱" if source_type == "telegram" else "📘"
        platform_name = "Telegram" if source_type == "telegram" else "VK"
        
        # Формируем приоритет
        priority_mark = ""
        if is_priority:
            priority_mark = "🔥 <b>Высокий приоритет</b> (Приоритетный ЖК)\n"
        
        # Формируем текст карточки
        content = (lead.get("content") or lead.get("intent") or post_text or "")[:400]
        if len(post_text or "") > 400:
            content += "…"
        
        pain_stage = lead.get("pain_stage", "")
        priority_score = lead.get("priority_score", 0)
        
        text_lines = [
            "🕵️ <b>НОВЫЙ ЛИД (на модерации)</b>",
            "",
            f"{platform_emoji} <b>Платформа:</b> {platform_name}",
            f"📍 <b>Локация:</b> {location}",
            priority_mark,
            f"📝 <b>Сообщение:</b> «{content}»",
            "",
        ]
        
        if pain_stage:
            text_lines.append(f"🔴 <b>Стадия боли:</b> {pain_stage}")
        if priority_score > 0:
            text_lines.append(f"⭐ <b>Приоритет:</b> {priority_score}/10")
        if anton_recommendation:
            text_lines.append(f"💡 <b>Рекомендация Антона:</b> {anton_recommendation[:200]}")
        
        text_lines.extend([
            "",
            f"🔗 <b>Пост:</b> {post_url}",
        ])
        
        if profile_url:
            if profile_url.startswith("http"):
                text_lines.append(f"👤 <b>Профиль:</b> <a href=\"{profile_url}\">открыть</a>")
            elif profile_url.startswith("tg://"):
                text_lines.append(f"👤 <b>Профиль:</b> <code>{profile_url}</code>")
        
        text = "\n".join(text_lines)
        
        # Формируем клавиатуру с кнопками модерации
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard_rows = [
            [
                InlineKeyboardButton(text="✅ Одобрить (Антон пишет)", callback_data=f"mod_approve_{lead_id}"),
            ],
            [
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"mod_edit_{lead_id}"),
                InlineKeyboardButton(text="🗑 Пропустить", callback_data=f"mod_skip_{lead_id}"),
            ],
        ]
        
        # Добавляем кнопку "Открыть пост", если есть ссылка
        if post_url:
            keyboard_rows.append([
                InlineKeyboardButton(text="🔗 Открыть пост", url=post_url[:500]),
            ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        
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
                    disable_notification=False,  # Всегда обычное уведомление для модерации
                )
                logger.info(f"📋 Карточка лида #{lead_id} отправлена на модерацию в админ-канал")
                return True
            finally:
                if _bot_for_send() is None and getattr(bot, "session", None):
                    try:
                        await bot.session.close()
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"❌ Не удалось отправить карточку лида на модерацию: {e}")
            return False

    async def _send_lead_card_to_group(
        self,
        lead: dict,
        lead_id: int,
        profile_url: str,
        post_url: str,
        card_header: str = "",
        anton_recommendation: str = "",
    ) -> bool:
        """Отправляет карточку лида в рабочую группу (топик «Горячие лиды») отдельным сообщением с кнопками.
        
        Тихие уведомления: если priority_score < 8, отправляется без звука (disable_notification=True).
        """
        from config import BOT_TOKEN, LEADS_GROUP_CHAT_ID, THREAD_ID_HOT_LEADS
        if not BOT_TOKEN or not LEADS_GROUP_CHAT_ID:
            logger.warning("⚠️ BOT_TOKEN или LEADS_GROUP_CHAT_ID не заданы — карточка в группу не отправлена")
            return False
        text = self._format_lead_card(lead, profile_url, card_header, anton_recommendation)
        
        # ── ТИХИЕ УВЕДОМЛЕНИЯ: priority_score < 8 → disable_notification = True ────
        priority_score = lead.get("priority_score", 0)
        disable_notification = priority_score < 8  # Тихие уведомления для низкоприоритетных лидов
        
        # ── КНОПКИ ДЕЙСТВИЙ ────────────────────────────────────────────────────────
        url_buttons = []
        
        # Кнопка "🔗 Перейти к сообщению" (обязательная)
        if post_url:
            url_buttons.append(InlineKeyboardButton(text="🔗 Перейти к сообщению", url=post_url[:500]))
        
        # Кнопка профиля (если есть)
        if profile_url and profile_url.startswith("http"):
            url_buttons.append(InlineKeyboardButton(text="👤 Профиль", url=profile_url))
        
        # Кнопки действий
        action_buttons = [
            InlineKeyboardButton(text="✅ В работу", callback_data=f"lead_take_work_{lead_id}"),
            InlineKeyboardButton(text="🛠 Ответить экспертно", callback_data=f"lead_expert_reply_{lead_id}"),
        ]
        
        # Формируем клавиатуру: первая строка - URL кнопки, вторая - действия
        keyboard_rows = []
        if url_buttons:
            keyboard_rows.append(url_buttons)
        if action_buttons:
            keyboard_rows.append(action_buttons)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows) if keyboard_rows else None
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
                    disable_notification=disable_notification,  # Тихие уведомления для priority_score < 8
                )
                if disable_notification:
                    logger.debug(f"🔇 Тихое уведомление отправлено для лида #{lead_id} (priority_score={priority_score})")
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
            "🕵️ <b>[ШПИОН] Новый лид</b>\n\n"
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
            "🔥 <b>[ШПИОН] ГОРЯЧИЙ ЛИД (AI Жюля)</b>\n\n"
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
        """True если текущее время 09:00–20:00 по МСК (UTC+3).
        ОТКЛЮЧЕНО ДЛЯ ТЕСТИРОВАНИЯ: Всегда возвращает True.
        """
        return True

    @staticmethod
    def _detect_priority_zhk_hot_static(text: str) -> tuple[bool, str]:
        """Определяет, является ли ЖК приоритетным (заглушка)"""
        if not text:
            return False, ""
        text_lower = text.lower()
        priority_zhk_names = ["династия", "зиларт", "высотка"]
        for zhk_name in priority_zhk_names:
            if zhk_name in text_lower:
                return True, zhk_name.title()
        return False, ""

    async def hunt(self):
        """Полный цикл: поиск → анализ → привлечение + проверка через AI Жюля и пересылка горячих лидов."""
        logger.info("🏹 LeadHunter: начало охоты за лидами...")
        logger.info("🧠 Использую YandexGPT для фильтрации лидов из ВК")

        # Принудительная очистка кеша парсера перед началом скана:
        # сбрасываем предыдущие отчёты и список чатов, чтобы не опираться на старые смещения/сканы.
        try:
            self.parser.last_scan_report = []
            self.parser.last_scan_chats_list = []
            self.parser.last_scan_at = datetime.now()
            logger.info("🔄 ScoutParser cache cleared before hunt (forced).")
        except Exception:
            pass

        # ── Проверка подключения к БД ────────────────────────────────────────────
        main_db = await self._ensure_db_connected()
        
        tg_posts = await self.parser.parse_telegram(db=main_db)
        vk_posts = await self.parser.parse_vk(db=main_db)  # Передаём БД для загрузки групп из target_resources
        
        # ── Глобальный поиск ВК через newsfeed.search ─────────────────────────────
        vk_global_posts = []
        try:
            vk_global_posts = await self.parser.search_vk_global(db=main_db, hours_back=24)
            if vk_global_posts:
                logger.info(f"🌍 VK Global Search: найдено {len(vk_global_posts)} лидов через newsfeed.search")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при глобальном поиске VK: {e}")
        
        all_posts = tg_posts + vk_posts + vk_global_posts

        # Если лидов не найдено, пробуем найти новые источники через Discovery (только Telegram)
        if not all_posts:
            logger.info("🔎 Лидов не найдено. Запуск Discovery для поиска новых Telegram-каналов...")
            # Поиск новых Telegram каналов
            new_sources = await self.discovery.find_new_sources()
            # VK-группы добавляются автоматически через search_vk_global выше
            added_count = 0
            activated_count = 0
            skipped_count = 0
            for source in new_sources:
                link = source["link"]
                title = source.get("title") or link
                
                # Проверяем подключение перед каждым запросом (на случай разрыва)
                main_db = await self._ensure_db_connected()
                
                # Проверяем, есть ли канал в БД
                try:
                    existing = await main_db.get_target_resource_by_link(link)
                except AttributeError as e:
                    logger.error(f"❌ Ошибка доступа к БД: {e}. Переподключаюсь...")
                    await main_db.connect()
                    existing = await main_db.get_target_resource_by_link(link)
                
                if existing:
                    # Канал уже есть в БД
                    existing_status = existing.get("status", "pending")
                    if existing_status != "active":
                        # Активируем канал, если он был archived или pending
                        try:
                            await main_db.set_target_status(existing["id"], "active")
                            activated_count += 1
                            logger.info(f"🔄 Discovery: активирован канал {title} (был: {existing_status})")
                        except Exception as e:
                            logger.warning(f"⚠️ Ошибка активации канала {link}: {e}")
                    else:
                        skipped_count += 1
                        logger.debug(f"⏭️ Discovery: канал уже активен {title}")
                else:
                    # Ресурс новый, добавляем
                    try:
                        resource_type = source.get("type", "telegram")  # По умолчанию telegram, может быть vk
                        await main_db.add_target_resource(
                            resource_type=resource_type,
                            link=link,
                            title=title,
                            notes="Найден через LeadHunter Discovery (глобальный поиск)",
                            status="active",  # Сразу активный, чтобы использовался для сканирования
                            participants_count=source.get("participants_count", 0),
                            geo_tag=source.get("geo_tag")  # Добавляем гео-тег, если есть
                        )
                        added_count += 1
                        logger.info(f"✅ Discovery: добавлен {resource_type} ресурс {title}")
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка добавления ресурса из Discovery {link}: {e}")
            
            # Итоговая статистика
            if added_count > 0:
                logger.info(f"📊 Discovery: добавлено {added_count} новых каналов в БД (статус: active)")
            if activated_count > 0:
                logger.info(f"🔄 Discovery: активировано {activated_count} каналов (были archived/pending)")
            if skipped_count > 0:
                logger.info(f"📋 Discovery: пропущено {skipped_count} каналов (уже активны)")

        # ── ИНКРЕМЕНТАЛЬНЫЙ ПОИСК: Используем last_post_id из БД ────────────────────
        # Логика skip_count удалена — теперь используется инкрементальный поиск через last_post_id
        # в scout_parser.py. SPY_SKIP_OLD_MESSAGES используется только для первого запуска.
        remaining = all_posts
        logger.info(f"🔎 LeadHunter: Найдено {len(remaining)} потенциальных постов для анализа")

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
        vk_global_count = len(vk_global_posts) if 'vk_global_posts' in locals() else 0
        logger.info(
            "🔍 ScoutParser: TG каналов=%s, VK групп=%s, VK global=%s, постов с ключевыми словами=%s",
            len(tg_ok), len(vk_ok), vk_global_count, len(all_posts)
        )

        from services.lead_hunter.database import HunterDatabase as LocalHunterDatabase
        # Анти-дубль: в рамках одного запуска не обрабатываем один и тот же post_id дважды
        _seen_post_keys: set[str] = set()
        _business_hours = self._is_business_hours_msk()
        logger.info("🕐 Бизнес-часы МСК: %s", "да (09:00–20:00)" if _business_hours else "нет — горячие лиды не отправляются")

        for post in all_posts:
            text = getattr(post, "text", "") or ""
            text_lower = text.lower()
            
            # Фильтрация по стоп-словам с исключением для "цена/сколько стоит"
            has_stop_word = any(sw in text_lower for sw in STOP_WORDS_ALL)
            is_priority_exception = any(exc in text_lower for exc in ["цена", "сколько стоит"])
            
            if has_stop_word and not is_priority_exception:
                logger.debug(f"🔇 Пост пропущен (стоп-слово): {text[:50]}...")
                continue

            _post_key = f"{getattr(post, 'source_type', '')}:{getattr(post, 'source_id', '')}:{getattr(post, 'post_id', '')}"
            if _post_key in _seen_post_keys:
                logger.debug("⏭️ Анти-дубль: post %s уже обработан в этом цикле", _post_key)
                continue
            _seen_post_keys.add(_post_key)

            # ── ПРОВЕРКА ДУБЛИКАТОВ ПО URL В БД ─────────────────────────────────────
            post_url = getattr(post, "url", "") or f"{getattr(post, 'source_type', '')}/{getattr(post, 'source_id', '')}/{getattr(post, 'post_id', '')}"
            try:
                db_path = os.path.abspath(POTENTIAL_LEADS_DB)
                hd = LocalHunterDatabase(db_path)
                await hd.connect()
                # Проверяем, есть ли такой URL в базе
                async with hd.conn.cursor() as cursor:
                    await cursor.execute("SELECT id FROM leads WHERE url = ?", (post_url,))
                    if await cursor.fetchone():
                        logger.debug(f"⏭️ Дубликат в БД: {post_url}")
                        await hd.conn.close()
                        continue
                await hd.conn.close()
            except Exception as e:
                logger.debug(f"Ошибка проверки дубликата в БД: {e}")

            # ── СТРОГАЯ ГЕО-ФИЛЬТРАЦИЯ (Москва и МО) ────────────────────────────────
            source_name = getattr(post, "source_name", "") or ""
            geo_keywords = ["москва", "московск", "мск", "м.о.", "мо", "зеленоград", "балашиха", "химки", "подольск", "королев", "мытищи", "люберцы", "электросталь", "коломна", "одинцово", "красногорск", "серпухов", "орехово-зуево", "щелково", "домодедово", "жуковский", "пушкино", "раменское", "ногинск", "долгопрудный", "реутов", "воскресенск", "чехов", "ивантеевка", "дубна", "егорьевск", "дмитров", "видное", "ступино", "павловский посад", "наро-фоминск", "фризино", "лыткарино", "дзержинский", "солнечногорск"]
            
            is_moscow_region = any(geo in source_name.lower() for geo in geo_keywords) or \
                               any(geo in text_lower for geo in geo_keywords)
            
            # Если это не Москва/МО и не приоритетный ЖК — пропускаем
            # Используем статический метод (который мы добавим ниже)
            is_priority_zhk_local, _ = LeadHunter._detect_priority_zhk_hot_static(text)
            
            if not is_moscow_region and not is_priority_zhk_local:
                logger.debug(f"🚫 Гео-фильтр: пост не относится к Москве/МО: {source_name}")
                continue
            
            analysis_data = {
                "geo_filtered": geo_filtered,
                "priority_score": 0,  # Будет определено через _analyze_intent
                "pain_stage": "ST-1",  # Будет определено через _analyze_intent
                "zhk_name": ""
            }
            
            # Если пост отфильтрован по гео — пропускаем
            if analysis_data.get("geo_filtered"):
                logger.debug("🚫 Пост отфильтрован по гео (не Москва/МО) — пропущен")
                continue
            
            score = analysis_data.get("priority_score", 0) / 10.0 # Приводим к 0.0 - 1.0 для совместимости
            pain_stage = analysis_data.get("pain_stage", "ST-1")

            # Глубокий анализ намерения через Yandex GPT агент (новая логика)
            try:
                analysis = await self._analyze_intent(getattr(post, "text", "") or "")
                # Обновляем analysis_data на основе результатов анализа
                if analysis.get("is_lead"):
                    analysis_data["priority_score"] = analysis.get("hotness", 0) * 2  # Преобразуем hotness (1-5) в priority_score (0-10)
                    analysis_data["pain_stage"] = analysis.get("pain_stage", "ST-1")
                    pain_stage = analysis_data["pain_stage"]
            except Exception as e:
                logger.debug("🔎 Анализ намерения не удался: %s", e)
                analysis = {"is_lead": False, "intent": "", "hotness": 0, "context_summary": "", "pain_stage": "ST-1"}

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
                        # Простая заглушка для определения приоритетного ЖК
                        is_zhk_hot, zhk_name = LeadHunter._detect_priority_zhk_hot_static(post.text or "")
                        zhk_name = zhk_name or analysis_data.get("zhk_name") or analysis.get("zhk_name") or ""

                        # ── Стадия боли ───────────────────────────────────────
                        pain_stage = analysis_data.get("pain_stage") or ""
                        pain_label = {
                            "ST-4": "⛔ Критично",
                            "ST-3": "🔴 Активная боль",
                            "ST-2": "🟡 Планирование",
                            "ST-1": "🟢 Интерес",
                        }.get(pain_stage, "")

                        # ── Генерируем проект ответа через Yandex GPT (с fallback на Router AI) ─────────
                        sales_draft = ""
                        try:
                            # Получаем данные о приоритете и платформе из target ресурса
                            is_priority_zhk = False
                            source_platform = "telegram"
                            if res:
                                is_priority_zhk = res.get("is_high_priority", 0) == 1
                                source_platform = res.get("platform") or res.get("type") or "telegram"
                            
                            sales_draft = await self._generate_sales_reply(
                                post_text=post.text or "",
                                pain_stage=pain_stage or "ST-2",
                                zhk_name=zhk_name,
                                intent=analysis.get("intent", ""),
                                context_summary=analysis.get("context_summary", ""),
                                platform=source_platform,
                                is_priority_zhk=is_priority_zhk,
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

            # ⚠️ АВТОМАТИЧЕСКАЯ ОТПРАВКА ОТКЛЮЧЕНА (Режим Модерации)
            # Вместо автоматической отправки все лиды отправляются в админ-канал для модерации
            # if score > 0.7:
            #     logger.info(f"🎯 Найден горячий лид! Score: {score}")
            #     message = self.parser.generate_outreach_message(post.source_type)
            #     await self.outreach.send_offer(post.source_type, post.source_id, message)

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
                                main_db = await self._ensure_db_connected()
                                res = await main_db.get_target_resource_by_link(source_link)
                                if res:
                                    is_high = res.get("is_high_priority") or 0
                                    geo_from_parser = source_name
                                    if hasattr(self.parser, 'extract_geo_header') and callable(self.parser.extract_geo_header):
                                        try:
                                            geo_from_parser = self.parser.extract_geo_header(post_text, source_name) or source_name
                                        except Exception:
                                            pass
                                    name_part = (res.get("geo_tag") or "").strip() or res.get("title") or geo_from_parser
                                    if is_high:
                                        card_header = f"🏙 ПРИОРИТЕТНЫЙ ЖК (Высотка)\n{name_part}" if name_part else "🏙 ПРИОРИТЕТНЫЙ ЖК (Высотка)"
                                    else:
                                        card_header = name_part
                                else:
                                    card_header = source_name
                                    if hasattr(self.parser, 'extract_geo_header') and callable(self.parser.extract_geo_header):
                                        try:
                                            card_header = self.parser.extract_geo_header(post_text, source_name) or source_name
                                        except Exception:
                                            pass
                            except Exception:
                                card_header = source_name
                                if hasattr(self.parser, 'extract_geo_header') and callable(self.parser.extract_geo_header):
                                    try:
                                        card_header = self.parser.extract_geo_header(post_text, source_name) or source_name
                                    except Exception:
                                        pass
                        else:
                            card_header = source_name
                            if hasattr(self.parser, 'extract_geo_header') and callable(self.parser.extract_geo_header):
                                try:
                                    card_header = self.parser.extract_geo_header(post_text, source_name) or source_name
                                except Exception:
                                    pass
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
                        main_db = await self._ensure_db_connected()
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
                        main_db = await self._ensure_db_connected()
                        notify_enabled = await main_db.get_setting("spy_notify_enabled", "1")
                        if notify_enabled == "1":
                            await self._send_lead_notify_to_admin(lead, source_name, profile_url or post_url)
                    except Exception:
                        pass
                    # Рекомендация Антона (Ассистент Продаж): по тексту подбираем скрипт из sales_templates
                    anton_recommendation = ""
                    try:
                        main_db = await self._ensure_db_connected()
                        anton_recommendation = await self._get_anton_recommendation(post_text, main_db)
                    except Exception:
                        pass
                    # ⚠️ АВТОМАТИЧЕСКАЯ ОТПРАВКА ЛС ОТКЛЮЧЕНА (Режим Модерации)
                    # Вместо автоматической отправки ЛС все лиды отправляются в админ-канал для модерации
                    # if author_id and author_id > 0:
                    #     lead_content = lead.get("content") or lead.get("intent") or post_text[:200]
                    #     await self._send_dm_to_user(author_id, post_url, lead_content)
                    
                    # ── ОБНОВЛЕННАЯ ЛОГИКА: Различение типов лидов для отправки ────────────
                    _lead_stage = lead.get("pain_stage") or ""
                    priority_score = lead.get("priority_score", 0)
                    
                    # Проверка на HOT_TRIGGERS в тексте поста
                    has_hot_trigger = False
                    if post_text:
                        from services.scout_parser import ScoutParser
                        hot_triggers = ScoutParser.HOT_TRIGGERS
                        import re
                        text_lower = post_text.lower()
                        for hot_trigger in hot_triggers:
                            if re.search(hot_trigger, text_lower):
                                has_hot_trigger = True
                                break
                    
                    # Горячий лид: HOT_TRIGGERS, ST-1/ST-2, или priority_score >= 3
                    _is_hot_lead = (
                        has_hot_trigger 
                        or _lead_stage in ("ST-1", "ST-2", "ST-3", "ST-4")
                        or priority_score >= 3
                        or lead.get("hotness", 0) >= 4
                    )
                    
                    # Обычный лид: priority_score < 3 и нет HOT_TRIGGERS
                    _is_regular_lead = (
                        not has_hot_trigger 
                        and priority_score < 3 
                        and _lead_stage not in ("ST-3", "ST-4")
                        and lead.get("hotness", 0) < 3
                    )
                    
                    # ── РЕЖИМ МОДЕРАЦИИ: Все лиды отправляются в админ-канал для модерации ────────
                    # Вместо автоматической отправки все лиды проходят через модерацию
                    
                    # Получаем данные о target из БД, если есть source_link
                    geo_tag_value = ""
                    is_priority_value = False
                    if post and hasattr(post, 'source_link') and post.source_link:
                        try:
                            main_db = await self._ensure_db_connected()
                            target_res = await main_db.get_target_resource_by_link(post.source_link)
                            if target_res:
                                geo_tag_value = target_res.get("geo_tag", "") or ""
                                is_priority_value = target_res.get("is_high_priority", 0) == 1
                        except Exception as e:
                            logger.debug(f"Не удалось получить данные target для source_link: {e}")
                    
                    # Если geo_tag не найден, используем card_header или извлекаем из текста
                    if not geo_tag_value:
                        geo_tag_value = card_header or ""
                        if post_text and hasattr(self, 'parser') and self.parser and hasattr(self.parser, 'extract_geo_header'):
                            try:
                                extracted = self.parser.extract_geo_header(post_text, geo_tag_value)
                                if extracted and extracted != geo_tag_value:
                                    geo_tag_value = extracted
                            except Exception:
                                pass
                    
                    if await self._send_lead_card_for_moderation(
                        lead=lead,
                        lead_id=lead_id,
                        profile_url=profile_url,
                        post_url=post_url,
                        card_header=card_header,
                        post_text=post_text,
                        source_type=post.source_type if hasattr(post, 'source_type') else "telegram",
                        source_link=post.source_link if hasattr(post, 'source_link') else "",
                        geo_tag=geo_tag_value,
                        is_priority=is_priority_value,
                        anton_recommendation=anton_recommendation
                    ):
                        cards_sent += 1
                        logger.info(f"📋 Карточка лида #{lead_id} отправлена на модерацию")
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
        # Отправляем только если есть реальные данные (просмотрено > 0 сообщений)
        try:
            from config import BOT_TOKEN, LEADS_GROUP_CHAT_ID, THREAD_ID_LOGS
            report = self.parser.get_last_scan_report()
            
            # Проверяем, есть ли реальные данные для отчёта
            tg_ok = [r for r in (self.parser.last_scan_report or []) if r.get("type") == "telegram" and r.get("status") == "ok"]
            vk_ok = [r for r in (self.parser.last_scan_report or []) if r.get("type") == "vk" and r.get("status") == "ok"]
            total_scanned = sum(r.get("scanned", 0) for r in tg_ok + vk_ok)
            
            # Отправляем отчёт только если есть данные или есть ошибки
            if BOT_TOKEN and LEADS_GROUP_CHAT_ID and report and "Отчёта ещё нет" not in report:
                # Не отправляем пустые отчёты (0 просмотрено сообщений)
                if total_scanned > 0 or any(r.get("status") == "error" for r in (tg_ok + vk_ok)):
                    bot = _bot_for_send()
                    if bot is None:
                        bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
                    try:
                        await bot.send_message(
                            LEADS_GROUP_CHAT_ID,
                            report,
                            message_thread_id=THREAD_ID_LOGS,
                        )
                        logger.info(f"📊 Отчёт отправлен в топик 'Логи': просмотрено {total_scanned} сообщений")
                    finally:
                        if _bot_for_send() is None and getattr(bot, "session", None):
                            try:
                                await bot.session.close()
                            except Exception:
                                pass
                else:
                    logger.debug("⏭️ Пропуск пустого отчёта (0 просмотрено сообщений)")
        except Exception as e:
            logger.warning("Не удалось отправить отчёт шпиона в группу: %s", e)

        # Файл со списком всех лидов (источник, превью текста, ссылка) — в тот же топик «Логи»
        # Отправляем только если есть реальные лиды
        if all_posts and len(all_posts) > 0:
            await self._send_raw_leads_file_to_group(all_posts)
        else:
            logger.debug("⏭️ Пропуск отправки файла лидов (0 лидов найдено)")

        # ── ИТОГОВОЕ ЛОГИРОВАНИЕ ЦИКЛА ────────────────────────────────────────────────
        # Подсчитываем статистику для итогового лога
        tg_scanned = sum(r.get("scanned", 0) for r in tg_ok if r.get("status") == "ok")
        vk_scanned = sum(r.get("scanned", 0) for r in vk_ok if r.get("status") == "ok")
        
        # Подсчитываем горячие лиды (priority_score >= 8 или ST-3/ST-4)
        hot_leads_count = 0
        try:
            main_db = await self._ensure_db_connected()
            # Получаем количество горячих лидов из БД за последний час
            async with main_db.conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT COUNT(*) FROM spy_leads 
                    WHERE created_at >= datetime('now', '-1 hour')
                    AND (priority_score >= 8 OR pain_stage IN ('ST-3', 'ST-4'))
                """)
                row = await cursor.fetchone()
                hot_leads_count = row[0] if row else 0
        except Exception as e:
            logger.debug(f"⚠️ Не удалось подсчитать горячие лиды для итогового лога: {e}")
            # Fallback: используем количество отправленных карточек
            hot_leads_count = cards_sent if 'cards_sent' in locals() else 0
        
        # Итоговое логирование цикла
        logger.info(
            f"✅ Cycle complete: {tg_scanned} TG messages scanned, {vk_scanned} VK posts scanned, {hot_leads_count} Hot leads found"
        )
        
        logger.info(f"🏹 LeadHunter: охота завершена. Обработано {len(all_posts)} постов.")
        
        # Сбрасываем статистику парсера после использования
        self.parser.total_scanned = 0
        self.parser.total_with_keywords = 0
        self.parser.total_leads = 0
        self.parser.total_hot_leads = 0
    
    async def send_regular_leads_summary(self) -> bool:
        """Отправка сводки обычных лидов (priority < 3) в рабочую группу.
        
        Собирает обычные лиды за последние 24 часа и отправляет их сводкой.
        Вызывается по расписанию: 10:00, 14:00, 19:00 МСК.
        
        Returns:
            True если сводка отправлена успешно, False в противном случае
        """
        from config import BOT_TOKEN, LEADS_GROUP_CHAT_ID, THREAD_ID_LOGS
        
        if not BOT_TOKEN or not LEADS_GROUP_CHAT_ID:
            logger.warning("⚠️ BOT_TOKEN или LEADS_GROUP_CHAT_ID не заданы — сводка не отправлена")
            return False
        
        try:
            main_db = await self._ensure_db_connected()
            regular_leads = await main_db.get_regular_leads_for_summary(since_hours=24)
            
            if not regular_leads:
                logger.debug("📋 Нет обычных лидов для сводки за последние 24 часа")
                return False
            
            # Формируем сводку
            lines = [
                f"📋 <b>Сводка обычных лидов</b> (за последние 24 часа)",
                f"Всего лидов: {len(regular_leads)}",
                "",
                "---",
                "",
            ]
            
            for i, lead in enumerate(regular_leads[:20], 1):  # Максимум 20 лидов в сводке
                source_name = lead.get("source_name", "—")
                text_preview = (lead.get("text") or "")[:200].replace("\n", " ")
                url = lead.get("url", "")
                priority = lead.get("priority_score", 0)
                stage = lead.get("pain_stage", "—")
                
                lines.append(f"<b>{i}. {source_name}</b>")
                lines.append(f"   Приоритет: {priority}/10 | Стадия: {stage}")
                if text_preview:
                    lines.append(f"   {text_preview}...")
                if url:
                    lines.append(f"   🔗 <a href='{url}'>Пост</a>")
                lines.append("")
            
            if len(regular_leads) > 20:
                lines.append(f"... и ещё {len(regular_leads) - 20} лидов")
            
            summary_text = "\n".join(lines)
            
            bot = _bot_for_send()
            if bot is None:
                bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            
            try:
                await bot.send_message(
                    LEADS_GROUP_CHAT_ID,
                    summary_text,
                    message_thread_id=THREAD_ID_LOGS,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                logger.info(f"✅ Сводка обычных лидов отправлена: {len(regular_leads)} лидов")
                return True
            finally:
                if _bot_for_send() is None and getattr(bot, "session", None):
                    try:
                        await bot.session.close()
                    except Exception:
                        pass
                        
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сводки обычных лидов: {e}")
            return False
    
    async def send_hot_leads_immediate(self) -> bool:
        """Немедленная отправка горячих лидов (HOT_TRIGGERS, ST-1/ST-2) в топик "Горячие лиды".
        
        Проверяет БД на наличие неотправленных горячих лидов и отправляет их.
        Вызывается при обнаружении нового горячего лида или по расписанию.
        
        Returns:
            True если лиды отправлены успешно, False в противном случае
        """
        from config import BOT_TOKEN, LEADS_GROUP_CHAT_ID, THREAD_ID_HOT_LEADS
        
        if not BOT_TOKEN or not LEADS_GROUP_CHAT_ID:
            logger.warning("⚠️ BOT_TOKEN или LEADS_GROUP_CHAT_ID не заданы — горячие лиды не отправлены")
            return False
        
        try:
            main_db = await self._ensure_db_connected()
            hot_leads = await main_db.get_hot_leads_for_immediate_send()
            
            if not hot_leads:
                return False
            
            sent_count = 0
            bot = _bot_for_send()
            if bot is None:
                bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            
            try:
                for lead in hot_leads[:10]:  # Максимум 10 лидов за раз
                    try:
                        lead_id = lead.get("id")
                        source_name = lead.get("source_name", "—")
                        text = (lead.get("text") or "")[:2000]
                        url = lead.get("url", "")
                        profile_url = lead.get("profile_url", "")
                        priority_score = lead.get("priority_score", 0)
                        pain_stage = lead.get("pain_stage", "")
                        
                        # Форматируем карточку лида с новым форматом
                        lead_data = {
                            "content": text,
                            "text": text,
                            "priority_score": priority_score,
                            "pain_stage": pain_stage,
                            "url": url,
                            "source_name": source_name,
                            "author_name": lead.get("author_name"),
                            "author_id": lead.get("author_id"),
                            "username": lead.get("username"),
                        }
                        card_text = self._format_lead_card(
                            lead_data,
                            profile_url=profile_url,
                            card_header=source_name
                        )
                        
                        # Кнопки (новый формат)
                        url_buttons = []
                        if url:
                            url_buttons.append(InlineKeyboardButton(text="🔗 Перейти к сообщению", url=url[:500]))
                        if profile_url and profile_url.startswith("http"):
                            url_buttons.append(InlineKeyboardButton(text="👤 Профиль", url=profile_url))
                        
                        action_buttons = [
                            InlineKeyboardButton(text="✅ В работу", callback_data=f"lead_take_work_{lead_id}"),
                            InlineKeyboardButton(text="🛠 Ответить экспертно", callback_data=f"lead_expert_reply_{lead_id}"),
                        ]
                        
                        keyboard_rows = []
                        if url_buttons:
                            keyboard_rows.append(url_buttons)
                        if action_buttons:
                            keyboard_rows.append(action_buttons)
                        
                        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows) if keyboard_rows else None
                        
                        # ── ТИХИЕ УВЕДОМЛЕНИЯ: priority_score < 8 → disable_notification = True ────
                        disable_notification = priority_score < 8  # Тихие уведомления для низкоприоритетных лидов
                        
                        await bot.send_message(
                            LEADS_GROUP_CHAT_ID,
                            card_text,
                            reply_markup=keyboard,
                            message_thread_id=THREAD_ID_HOT_LEADS,
                            parse_mode="HTML",
                            disable_notification=disable_notification,  # Тихие уведомления для priority_score < 8
                        )
                        
                        if disable_notification:
                            logger.debug(f"🔇 Тихое уведомление отправлено для лида #{lead_id} (priority_score={priority_score})")
                        
                        # Отмечаем как отправленный
                        await main_db.mark_lead_sent_to_hot_leads(lead_id)
                        sent_count += 1
                        
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки горячего лида {lead.get('id')}: {e}")
                        continue
                
                if sent_count > 0:
                    logger.info(f"🔥 Отправлено горячих лидов в топик 'Горячие лиды': {sent_count}")
                
                return sent_count > 0
                
            finally:
                if _bot_for_send() is None and getattr(bot, "session", None):
                    try:
                        await bot.session.close()
                    except Exception:
                        pass
                        
        except Exception as e:
            logger.error(f"❌ Ошибка отправки горячих лидов: {e}")
            return False
    
    async def send_daily_report(self) -> bool:
        """Отправка итогового отчёта за день в рабочую группу.
        
        Вызывается по расписанию: 9:00, 14:00, 19:00 МСК.
        Показывает статистику за последние 24 часа.
        
        Returns:
            True если отчёт отправлен успешно, False в противном случае
        """
        from config import BOT_TOKEN, LEADS_GROUP_CHAT_ID, THREAD_ID_LOGS
        
        if not BOT_TOKEN or not LEADS_GROUP_CHAT_ID:
            logger.warning("⚠️ BOT_TOKEN или LEADS_GROUP_CHAT_ID не заданы — отчёт не отправлен")
            return False
        
        try:
            main_db = await self._ensure_db_connected()
            
            # Получаем статистику за последние 24 часа
            total_leads_24h = await main_db.get_spy_leads_count_24h()
            recent_leads = await main_db.get_spy_leads_since_hours(since_hours=24)
            
            # Разделяем на горячие и обычные
            hot_leads = [l for l in recent_leads if (l.get("priority_score") or 0) >= 3]
            regular_leads = [l for l in recent_leads if (l.get("priority_score") or 0) < 3]
            
            # Получаем отчёт парсера о последнем скане
            parser_report = self.parser.get_last_scan_report()
            
            # Формируем итоговый отчёт
            lines = [
                "📊 <b>ИТОГОВЫЙ ОТЧЁТ ШПИОНА</b>",
                f"⏱ За последние 24 часа",
                "",
                f"🎯 <b>Всего найдено лидов:</b> {total_leads_24h}",
                f"🔥 <b>Горячих (priority ≥ 3):</b> {len(hot_leads)}",
                f"📋 <b>Обычных:</b> {len(regular_leads)}",
                "",
                "─" * 30,
                "",
            ]
            
            # Добавляем отчёт парсера о последнем скане
            if parser_report and "Отчёта ещё нет" not in parser_report:
                lines.append("<b>Последний скан:</b>")
                lines.append(parser_report.replace("<b>", "").replace("</b>", ""))
                lines.append("")
            
            # Показываем последние горячие лиды (до 5 штук)
            if hot_leads:
                lines.append("<b>🔥 Последние горячие лиды:</b>")
                for i, lead in enumerate(hot_leads[:5], 1):
                    source_name = lead.get("source_name", "—")
                    text_preview = (lead.get("text") or "")[:100].replace("\n", " ")
                    url = lead.get("url", "")
                    priority = lead.get("priority_score", 0)
                    stage = lead.get("pain_stage", "—")
                    
                    lines.append(f"{i}. <b>{source_name}</b> (приоритет: {priority}, стадия: {stage})")
                    if text_preview:
                        lines.append(f"   {text_preview}...")
                    if url:
                        lines.append(f"   🔗 <a href='{url}'>Пост</a>")
                    lines.append("")
            
            if len(hot_leads) > 5:
                lines.append(f"... и ещё {len(hot_leads) - 5} горячих лидов")
            
            report_text = "\n".join(lines)
            
            bot = _bot_for_send()
            if bot is None:
                bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            
            try:
                await bot.send_message(
                    LEADS_GROUP_CHAT_ID,
                    report_text,
                    message_thread_id=THREAD_ID_LOGS,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                logger.info(f"✅ Итоговый отчёт отправлен: {total_leads_24h} лидов за 24 часа")
                return True
            finally:
                if _bot_for_send() is None and getattr(bot, "session", None):
                    try:
                        await bot.session.close()
                    except Exception:
                        pass
                        
        except Exception as e:
            logger.error(f"❌ Ошибка отправки итогового отчёта: {e}")
            return False
