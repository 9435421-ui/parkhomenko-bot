"""
ScoutParser — парсинг Telegram-чатов и VK-групп для поиска лидов.

ВАЖНЫЕ ИСПРАВЛЕНИЯ (март 2026):
1. async for msg in client.iter_messages() — был синхронный for, молча возвращал []
2. get_last_scan_report() — возвращает строку (было dict → TypeError при send_message)
3. Имя сессии: 'anton_parser' (единое во всём проекте)
4. Метод start()/stop() для управления Telethon-клиентом из bot_spy.py
"""
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    ChatAdminRequiredError,
    ChannelPrivateError,
    UsernameNotOccupiedError,
)
from telethon.tl.types import Channel, Chat, User

from config import (
    API_ID,
    API_HASH,
    VK_TOKEN,
    SCOUT_TG_KEYWORDS,
    SCOUT_VK_KEYWORDS,
    SCAN_LIMIT,
)
from database.db import db

logger = logging.getLogger(__name__)

# ─── Константы фильтрации ─────────────────────────────────────────────────────

SESSION_NAME = "anton_parser"   # единое имя сессии во всём проекте

STOP_KEYWORDS = [
    "продам", "сдам", "аренда", "куплю", "ищу квартиру",
    "риелтор", "агентство", "новостройка", "скидка", "акция",
    "реклама", "объявление", "прайс", "прайслист",
]

AD_STOP_WORDS = [
    "подписывайтесь", "переходите по ссылке", "наш канал",
    "наш сайт", "оставьте заявку", "звоните нам",
    "узнайте больше", "специальное предложение",
]

HOT_TRIGGERS = [
    r"предписание\s+МЖИ",
    r"штраф\s+за\s+перепланировку",
    r"блокировка\s+сделки",
    r"узаконить\s+перепланировку",
    r"инспектор\s+МЖИ",
    r"согласовать\s+перепланировку",
    r"проект\s+перепланировки",
    r"заказать\s+проект",
    r"нужен\s+проект",
    r"кто\s+согласовывал",
]

TECHNICAL_TERMS = [
    r"перепланиров",
    r"согласовани",
    r"узакони",
    r"мжи",
    r"бти",
    r"акт\s+скрытых",
    r"снос\s+(стен|подоконн|блока)",
    r"объединен",
    r"нежилое\s+помещен",
    r"план\s+(квартир|помещен)",
    r"мокрая\s+зона",
]

COMMERCIAL_MARKERS = [
    r"стоимость",
    r"сколько\s+стоит",
    r"цена",
    r"нужен\s+проект",
    r"помогите",
    r"к\s+кому\s+обратиться",
    r"предписание",
    r"инспектор",
    r"заказать\s+проект",
    r"оформить\s+перепланировку",
    r"согласовал\w*",
    r"узаконил\w*",
]

QUESTION_PATTERNS = [
    r"кто\s+делал",
    r"как\s+согласовать",
    r"подскажите",
    r"\?\s*$",
    r"кто\s+(согласовывал|оформлял|делал|заказывал)",
    r"как\s+(согласовать|узаконить|оформить|сделать)",
    r"есть\s+кто",
    r"посоветуйте",
    r"помогите\s+разобраться",
]


class ScoutParser:
    """Парсер Telegram-чатов и VK-групп для поиска потенциальных лидов."""

    def __init__(self):
        self._client: Optional[TelegramClient] = None
        self._client_started: bool = False
        self.last_scan_report: Optional[list] = None
        self.last_scan_at: Optional[datetime] = None

    # ─── Управление клиентом ──────────────────────────────────────────────────

    async def start(self) -> None:
        """Инициализирует и подключает Telethon-клиент."""
        if self._client_started:
            return

        if not API_ID or not API_HASH:
            logger.warning("⚠️ API_ID и API_HASH не заданы в .env. Telegram сканирование будет пропущено.")
            return

        session_file = f"{SESSION_NAME}.session"
        if not os.path.exists(session_file):
            logger.warning("⚠️ Файл сессии '%s' не найден. Telegram сканирование будет пропущено.", session_file)
            return

        self._client = TelegramClient(SESSION_NAME, int(API_ID), API_HASH)
        await self._client.connect()

        try:
            if not await self._client.is_user_authorized():
                logger.warning("⚠️ Telethon session is not authorized! Telegram scanning will be skipped.")
                return
        except Exception as e:
            logger.warning(f"⚠️ Error checking Telegram authorization: {e}. Telegram scanning will be skipped.")
            return

        self._client_started = True
        me = await self._client.get_me()
        logger.info("✅ Telethon подключён как @%s (ID: %s)", me.username or me.id, me.id)

    async def stop(self) -> None:
        """Корректно отключает Telethon-клиент."""
        if self._client and self._client_started:
            await self._client.disconnect()
            self._client_started = False
            logger.info("Telethon-клиент отключён")

    def _ensure_client(self) -> TelegramClient:
        if not self._client or not self._client_started:
            raise RuntimeError(
                "Telethon-клиент не запущен. Вызовите await scout_parser.start() перед парсингом."
            )
        return self._client

    # ─── Фильтрация ───────────────────────────────────────────────────────────

    def _is_stop_word(self, text: str) -> bool:
        tl = text.lower()
        return any(w in tl for w in STOP_KEYWORDS) or any(w in tl for w in AD_STOP_WORDS)

    def _count_links(self, text: str) -> int:
        return len(re.findall(r'https?://|t\.me/|@\w{5,}', text))

    def _matches_any(self, text: str, patterns: list) -> bool:
        tl = text.lower()
        return any(re.search(p, tl) for p in patterns)

    def _is_hot(self, text: str) -> bool:
        return self._matches_any(text, HOT_TRIGGERS)

    def _has_technical(self, text: str) -> bool:
        return self._matches_any(text, TECHNICAL_TERMS)

    def _has_commercial(self, text: str) -> bool:
        return self._matches_any(text, COMMERCIAL_MARKERS)

    def _has_question(self, text: str) -> bool:
        return self._matches_any(text, QUESTION_PATTERNS)

    def detect_lead(self, text: str, source_type: str = "telegram") -> Optional[str]:
        """
        Определяет, является ли сообщение лидом.
        Возвращает 'hot', 'warm' или None.
        """
        if not text or len(text.strip()) < 20:
            return None

        # Длинные тексты — скорее статьи/объявления
        if len(text) > 1500:
            return None

        if self._is_stop_word(text):
            return None

        # Больше 2 ссылок — реклама
        if self._count_links(text) > 2:
            return None

        # Горячий триггер — безусловный лид
        if self._is_hot(text):
            return "hot"

        has_tech = self._has_technical(text)
        has_comm = self._has_commercial(text)
        has_q = self._has_question(text)

        if source_type == "vk":
            # Для VK достаточно технического термина
            if has_tech:
                return "warm"
        else:
            # Для Telegram: тех.термин + (вопрос или коммерческий маркер)
            if has_tech and (has_q or has_comm):
                return "warm"

        return None

    # ─── Парсинг Telegram ─────────────────────────────────────────────────────

    async def parse_telegram(
        self,
        link: str,
        limit: int = SCAN_LIMIT,
        min_date: Optional[datetime] = None,
    ) -> list:
        """
        Парсит чат/группу Telegram, возвращает список найденных лидов.

        ИСПРАВЛЕНИЕ: async for (был синхронный for — молча возвращал []).
        """
        client = self._ensure_client()
        results = []

        if min_date is None:
            min_date = datetime.utcnow() - timedelta(hours=24)

        try:
            entity = await client.get_entity(link)
        except (UsernameNotOccupiedError, ChannelPrivateError, ValueError) as e:
            logger.warning("Не удалось получить сущность '%s': %s", link, e)
            return results
        except Exception as e:
            logger.error("Ошибка get_entity('%s'): %s", link, e)
            return results

        # Пропускаем broadcast-каналы (не чаты) — там нет живых пользователей
        is_broadcast = (
            isinstance(entity, Channel)
            and getattr(entity, 'broadcast', False)
            and not getattr(entity, 'megagroup', False)
        )
        if is_broadcast:
            logger.debug("Пропускаем broadcast-канал: %s", link)
            return results

        iter_params = {"limit": limit}

        try:
            # ✅ ИСПРАВЛЕНО: async for вместо for
            async for msg in client.iter_messages(entity, **iter_params):
                # Останавливаемся, если сообщение старше min_date
                if msg.date and msg.date.replace(tzinfo=None) < min_date:
                    break

                # Только сообщения от живых пользователей
                if not isinstance(msg.sender, User):
                    continue

                text = msg.text or msg.message or ""
                if not text:
                    continue

                lead_type = self.detect_lead(text, source_type="telegram")
                if lead_type:
                    results.append({
                        "type": "telegram",
                        "source": link,
                        "message_id": msg.id,
                        "user_id": msg.sender_id,
                        "username": getattr(msg.sender, 'username', None),
                        "first_name": getattr(msg.sender, 'first_name', ''),
                        "text": text[:500],
                        "lead_type": lead_type,
                        "date": msg.date.isoformat() if msg.date else None,
                    })

        except FloodWaitError as e:
            logger.warning("FloodWait %s сек для '%s'", e.seconds, link)
            await asyncio.sleep(e.seconds)
        except ChatAdminRequiredError:
            logger.warning("Нет доступа к '%s' (требуются права админа)", link)
        except Exception as e:
            logger.error("Ошибка парсинга '%s': %s", link, e)

        logger.info("Telegram '%s': найдено %d лидов из %d сообщений", link, len(results), limit)
        return results

    # ─── Парсинг VK ──────────────────────────────────────────────────────────

    async def parse_vk(self, group_id: str, count: int = 50) -> list:
        """Парсит стену VK-группы."""
        if not VK_TOKEN:
            logger.warning("VK_TOKEN не задан, парсинг VK пропущен")
            return []

        results = []
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "owner_id": f"-{group_id}",
                    "count": count,
                    "access_token": VK_TOKEN,
                    "v": "5.199",
                }
                async with session.get(
                    "https://api.vk.com/method/wall.get",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    data = await resp.json()

                if "error" in data:
                    logger.error("VK API error для группы %s: %s", group_id, data["error"])
                    return results

                for item in data.get("response", {}).get("items", []):
                    text = item.get("text", "")
                    if not text:
                        continue
                    lead_type = self.detect_lead(text, source_type="vk")
                    if lead_type:
                        results.append({
                            "type": "vk",
                            "source": f"vk_group_{group_id}",
                            "post_id": item.get("id"),
                            "from_id": item.get("from_id"),
                            "text": text[:500],
                            "lead_type": lead_type,
                            "date": str(item.get("date")),
                        })

        except Exception as e:
            logger.error("Ошибка парсинга VK группы %s: %s", group_id, e)

        logger.info("VK группа %s: найдено %d лидов", group_id, len(results))
        return results

    async def parse_vk_comments(self, group_id: str, post_id: int, count: int = 50) -> list:
        """Парсит комментарии под постом VK."""
        if not VK_TOKEN:
            return []

        results = []
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "owner_id": f"-{group_id}",
                    "post_id": post_id,
                    "count": count,
                    "access_token": VK_TOKEN,
                    "v": "5.199",
                }
                async with session.get(
                    "https://api.vk.com/method/wall.getComments",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    data = await resp.json()

                if "error" in data:
                    return results

                for item in data.get("response", {}).get("items", []):
                    # Только реальные пользователи (from_id > 0)
                    if item.get("from_id", 0) <= 0:
                        continue
                    text = item.get("text", "")
                    if not text:
                        continue
                    lead_type = self.detect_lead(text, source_type="vk")
                    if lead_type:
                        results.append({
                            "type": "vk_comment",
                            "source": f"vk_group_{group_id}_post_{post_id}",
                            "comment_id": item.get("id"),
                            "from_id": item.get("from_id"),
                            "text": text[:500],
                            "lead_type": lead_type,
                            "date": str(item.get("date")),
                        })
        except Exception as e:
            logger.error("Ошибка парсинга комментариев VK %s/%s: %s", group_id, post_id, e)

        return results

    # ─── Полный цикл сканирования ─────────────────────────────────────────────

    async def scan_all(self) -> list:
        """
        Запускает полный цикл сканирования всех активных источников из БД.
        Возвращает суммарный список найденных лидов.
        """
        all_leads = []
        scan_results = []

        try:
            targets = await db.get_active_targets_for_scout()
        except Exception as e:
            logger.error("Не удалось получить источники из БД: %s", e)
            return all_leads

        tg_targets = [t for t in targets if t.get("platform") in ("telegram", "tg")]
        vk_targets = [t for t in targets if t.get("platform") == "vk"]

        logger.info(
            "🕵️ Сканирование: %d Telegram + %d VK источников",
            len(tg_targets), len(vk_targets)
        )

        # Telegram
        if self._client_started:
            for target in tg_targets:
                link = target.get("link", "")
                if not link:
                    continue
                try:
                    leads = await self.parse_telegram(link)
                    all_leads.extend(leads)
                    scan_results.append({
                        "type": "telegram",
                        "source": link,
                        "posts": len(leads),
                        "ok": True,
                    })
                except Exception as e:
                    logger.error("Ошибка скана TG '%s': %s", link, e)
                    scan_results.append({"type": "telegram", "source": link, "posts": 0, "ok": False})

                # Пауза между запросами — защита от FloodWait
                await asyncio.sleep(2)
        else:
            logger.warning("⚠️ Telegram session not started, skipping Telegram scanning")
            scan_results.append({
                "type": "telegram",
                "source": "Not authorized",
                "posts": 0,
                "ok": False,
            })

        # VK
        for target in vk_targets:
            group_id = target.get("link", "").lstrip("-")
            if not group_id:
                continue
            try:
                leads = await self.parse_vk(group_id)
                all_leads.extend(leads)
                scan_results.append({
                    "type": "vk",
                    "source": group_id,
                    "posts": len(leads),
                    "ok": True,
                })
            except Exception as e:
                logger.error("Ошибка скана VK '%s': %s", group_id, e)
                scan_results.append({"type": "vk", "source": group_id, "posts": 0, "ok": False})

            await asyncio.sleep(1)

        self.last_scan_report = scan_results
        self.last_scan_at = datetime.utcnow()

        logger.info("✅ Скан завершён: найдено %d лидов итого", len(all_leads))
        return all_leads

    # ─── Отчёт ────────────────────────────────────────────────────────────────

    def get_last_scan_report(self) -> str:
        """
        Возвращает форматированный текстовый отчёт о последнем скане.

        ИСПРАВЛЕНИЕ: ранее возвращал dict → TypeError при bot.send_message().
        Теперь всегда возвращает строку, готовую для отправки в Telegram.
        """
        if not self.last_scan_report:
            return "Отчёта ещё нет — шпион ещё не запускался."

        tg_results = [r for r in self.last_scan_report if r.get("type") == "telegram"]
        vk_results = [r for r in self.last_scan_report if r.get("type") in ("vk", "vk_comment")]
        total_leads = sum(r.get("posts", 0) for r in self.last_scan_report)
        tg_errors = sum(1 for r in tg_results if not r.get("ok", True))
        vk_errors = sum(1 for r in vk_results if not r.get("ok", True))

        scan_time = (
            self.last_scan_at.strftime('%d.%m.%Y %H:%M UTC')
            if self.last_scan_at
            else "—"
        )

        # Check if Telegram was skipped due to authorization issues
        tg_skipped = any(r.get("source") == "Not authorized" for r in tg_results)

        lines = [
            "🕵️ <b>Отчёт шпиона ТЕРИОН</b>",
            "",
        ]

        if tg_skipped:
            lines.append("📱 <b>Telegram:</b> Не авторизован (пропущено)")
        else:
            lines.append(f"📱 <b>Telegram:</b> {len(tg_results)} источников"
                        + (f" ({tg_errors} ошибок)" if tg_errors else ""))

        lines.extend([
            f"📘 <b>VK:</b> {len(vk_results)} источников"
            + (f" ({vk_errors} ошибок)" if vk_errors else ""),
            f"🎯 <b>Найдено лидов:</b> {total_leads}",
            f"🕐 <b>Время скана:</b> {scan_time}",
        ])

        # Детали по источникам (первые 10, чтобы не превысить лимит Telegram)
        sources_with_leads = [r for r in self.last_scan_report if r.get("posts", 0) > 0]
        if sources_with_leads:
            lines.append("")
            lines.append("📌 <b>Источники с лидами:</b>")
            for r in sources_with_leads[:10]:
                icon = "📱" if r.get("type") == "telegram" else "📘"
                lines.append(f"{icon} {r['source']}: {r['posts']} лид(ов)")

        return "\n".join(lines)


# ─── Singleton ────────────────────────────────────────────────────────────────

scout_parser = ScoutParser()
