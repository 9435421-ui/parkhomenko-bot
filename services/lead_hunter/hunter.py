import os
import re
import json
import time
import logging
import asyncio
import aiohttp
from typing import List, Dict, Optional
from .database import HunterDatabase

logger = logging.getLogger(__name__)

try:
    from utils.router_ai import router_ai
except ImportError:
    router_ai = None

# ──────────────────────────────────────────────
# КОНФИГУРАЦИЯ DISCOVERY
# ──────────────────────────────────────────────

VK_API_BASE = "https://api.vk.com/method"
VK_API_VERSION = "5.131"

# Поисковые запросы — жилые паблики ЖК, НЕ конкуренты
DISCOVERY_QUERIES = [
    "жители ЖК Москва",
    "соседи Москва чат",
    "чат дома Москва",
    "жильцы Москва паблик",
    "ЖК Москва жители",
    "районный чат Москва",
    "новостройка жители Москва",
    "ЖК чат жильцы",
    "управляющая компания жители",
    "наш двор Москва",
    "форум жильцов Москва",
    "ТСЖ Москва жители",
    "жители микрорайон Москва",
    "новостройки Москва переехали",
    "соседи район Москва",
]

# Стоп-слова: это конкуренты — пропускаем
COMPETITOR_KEYWORDS = [
    "перепланировк", "согласован", "дизайн-проект", "дизайн проект",
    "архитектурное бюро", "проектирование квартир", "технический план",
    "кадастровый инженер", "бти услуги", "риэлтор",
]

# Маркеры целевой аудитории — хотя бы один должен присутствовать
TARGET_KEYWORDS = [
    "жк", "жител", "сосед", "двор", "подъезд",
    "жильц", "тсж", "район", "микрорайон", "новостройк",
    "квартал", "корпус", "управляющ",
]

MIN_MEMBERS = 100
MAX_MEMBERS = 500_000


# ──────────────────────────────────────────────
# LEAD HUNTER
# ──────────────────────────────────────────────

class LeadHunter:
    def __init__(self, db: HunterDatabase = None):
        # db опциональный — если не передан, создаём сами
        if db is None:
            db = HunterDatabase()
        self.db = db

        self.geo_keywords = [
            "москва", "мск", "подмосковье", "мо", "жк", "корпус", "ремонт в москве",
            "нежилое помещение", "коммерция", "антресоль", "отдельный вход", "общепит",
            "кафе", "офис", "изменение назначения",
        ]
        self.lead_phrases = [
            "своими руками",
            "сломали стену",
            "перенесли радиатор",
            "залили пол",
            "хотим объединить",
        ]

    # ──────────────────────────────────────────
    # ОСНОВНАЯ ОХОТА ЗА ЛИДАМИ
    # ──────────────────────────────────────────

    async def hunt(self, messages: List[Dict] = None):
        """Анализ сообщений на предмет лидов. Вызывается планировщиком каждые 30 мин."""
        if not messages:
            # Если вызван без аргументов — пробуем получить сообщения из scout_parser
            try:
                from services.scout_parser import ScoutParser
                parser = ScoutParser()
                messages = await parser.scan_vk_groups()
            except Exception as e:
                logger.warning(f"hunt(): не удалось получить сообщения: {e}")
                messages = []

        if not messages:
            return []

        results = []
        for msg in messages:
            text = (msg.get('text') or '').strip()
            text_lower = text.lower()
            has_lead_phrase = any(p in text_lower for p in self.lead_phrases)
            analysis = await self._analyze_intent(text)
            hotness = max(analysis.get('hotness', 3), 4 if has_lead_phrase else 0)

            pain_stage = analysis.get("pain_stage", "ST-2" if hotness >= 3 else "ST-1")
            if has_lead_phrase:
                pain_stage = "ST-3"

            if hotness >= 2 or analysis.get('is_lead') or has_lead_phrase:
                lead_data = {
                    'url': msg.get('url', ''),
                    'content': text,
                    'intent': analysis.get('intent', 'DIY/ремонт') if has_lead_phrase else analysis.get('intent', '—'),
                    'hotness': hotness,
                    'geo': "Москва/МО" if self._check_geo(text) else "Не указано",
                    'context_summary': analysis.get('context_summary', '') or ('по фразе: ' + next((p for p in self.lead_phrases if p in text_lower), '')),
                    'recommendation': analysis.get('recommendation', ''),
                    'pain_level': analysis.get('pain_level', min(hotness, 5)),
                    'pain_stage': pain_stage,
                    'priority_score': hotness * 2 if hotness <= 5 else hotness,
                }
                if not self.db.conn:
                    await self.db.connect()
                if await self.db.save_lead(lead_data):
                    results.append(lead_data)
        return results

    # ──────────────────────────────────────────
    # DISCOVERY: поиск жилых пабликов ЖК в VK
    # ──────────────────────────────────────────

    async def run_discovery(self) -> dict:
        """
        Вызывается планировщиком раз в 24 часа.
        Ищет жилые паблики ЖК Москвы в VK, добавляет в target_resources.
        Удаляет конкурентов из БД.
        """
        vk_token = os.getenv("VK_TOKEN", "")
        db_path = os.getenv("DB_PATH", "parkhomenko_bot.db")

        stats = {
            "removed": 0, "found": 0, "added": 0,
            "skipped_competitor": 0, "skipped_invalid": 0, "skipped_exists": 0,
        }

        if not vk_token:
            logger.error("run_discovery: VK_TOKEN не задан")
            return stats

        logger.info("🔍 Discovery: старт поиска жилых пабликов ЖК...")

        try:
            import aiosqlite
            async with aiosqlite.connect(db_path) as conn:
                # Шаг 1: чистим конкурентов
                stats["removed"] = await self._remove_competitors(conn)
                logger.info(f"Discovery: удалено конкурентов из БД: {stats['removed']}")

                # Шаг 2: уже известные ссылки
                async with conn.execute("SELECT link FROM target_resources") as cur:
                    rows = await cur.fetchall()
                existing = {r[0] for r in rows}

                # Шаг 3: поиск по всем запросам
                all_groups: dict = {}
                async with aiohttp.ClientSession() as session:
                    for query in DISCOVERY_QUERIES:
                        await asyncio.sleep(0.4)
                        groups = await self._vk_search_groups(session, vk_token, query)
                        for g in groups:
                            gid = g.get("id")
                            if gid and gid not in all_groups:
                                all_groups[gid] = g

                stats["found"] = len(all_groups)
                logger.info(f"Discovery: найдено уникальных групп: {stats['found']}")

                # Шаг 4: фильтрация и добавление
                for group in all_groups.values():
                    link = f"https://vk.com/club{group.get('id')}"

                    if link in existing:
                        stats["skipped_exists"] += 1
                        continue
                    if self._is_competitor(group):
                        stats["skipped_competitor"] += 1
                        continue
                    if not self._is_valid_group(group) or not self._is_target_group(group):
                        stats["skipped_invalid"] += 1
                        continue

                    priority = self._score_group(group)
                    added = await self._add_group_to_db(conn, group, priority)
                    if added:
                        stats["added"] += 1
                        logger.info(
                            f"✅ Discovery добавил: {group.get('name')} | "
                            f"{group.get('members_count')} уч. | приоритет: {priority}"
                        )
                    else:
                        stats["skipped_exists"] += 1

        except Exception as e:
            logger.error(f"Discovery: критическая ошибка: {e}", exc_info=True)

        logger.info(
            f"Discovery завершён: удалено {stats['removed']}, "
            f"добавлено {stats['added']} из {stats['found']} найденных"
        )
        return stats

    # ──────────────────────────────────────────
    # ЕЖЕНЕДЕЛЬНЫЙ ИНСАЙТ (воскресенье 18:00)
    # ──────────────────────────────────────────

    async def generate_weekly_insight(self) -> str:
        """
        Генерирует еженедельный аналитический инсайт по лидам за неделю.
        Вызывается планировщиком: воскресенье, 18:00.
        """
        logger.info("📊 Генерация еженедельного инсайта...")
        try:
            if not self.db.conn:
                await self.db.connect()

            hot_leads = await self.db.get_latest_hot_leads(limit=10)

            if not hot_leads:
                insight = "📊 За эту неделю горячих лидов не обнаружено. Расширяем зону поиска."
                logger.info("generate_weekly_insight: лидов нет")
                return insight

            # Формируем сводку для AI
            leads_text = "\n".join([
                f"- {l.get('content', '')[:150]} (hotness: {l.get('hotness')})"
                for l in hot_leads
            ])

            prompt = (
                "Ты — аналитик по рынку перепланировок Москвы. "
                "Вот топ лидов за неделю из чатов жильцов:\n\n"
                f"{leads_text}\n\n"
                "Напиши короткий еженедельный инсайт (3–5 предложений): "
                "какие боли чаще всего встречаются, какой тип клиентов самый активный, "
                "какую тему стоит использовать в контенте на следующей неделе."
            )

            insight = ""
            if router_ai:
                try:
                    insight = await router_ai.generate_response(prompt)
                except Exception as e:
                    logger.warning(f"generate_weekly_insight router_ai: {e}")

            if not insight:
                # Fallback: простая статистика без AI
                avg_hotness = sum(l.get('hotness', 0) for l in hot_leads) / len(hot_leads)
                insight = (
                    f"📊 Еженедельный инсайт ТЕРИОН\n\n"
                    f"Проанализировано лидов: {len(hot_leads)}\n"
                    f"Средняя температура: {avg_hotness:.1f}/5\n"
                    f"Топ-запрос: {hot_leads[0].get('content', '')[:100]}\n\n"
                    f"Рекомендация: усилить контент по теме объединения комнат и переноса санузла."
                )

            logger.info("generate_weekly_insight: инсайт готов")
            return insight

        except Exception as e:
            logger.error(f"generate_weekly_insight: {e}", exc_info=True)
            return f"⚠️ Не удалось сгенерировать инсайт: {e}"

    # ──────────────────────────────────────────
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ DISCOVERY
    # ──────────────────────────────────────────

    async def _vk_search_groups(self, session: aiohttp.ClientSession, vk_token: str, query: str) -> list:
        params = {
            "q": query, "type": "group", "country_id": 1, "city_id": 1,
            "count": 20, "fields": "members_count,description,status,activity",
            "access_token": vk_token, "v": VK_API_VERSION,
        }
        try:
            async with session.get(
                f"{VK_API_BASE}/groups.search", params=params,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                if "error" in data:
                    logger.warning(f"VK API error '{query}': {data['error']}")
                    return []
                return data.get("response", {}).get("items", [])
        except Exception as e:
            logger.error(f"VK search '{query}': {e}")
            return []

    def _is_competitor(self, group: dict) -> bool:
        text = " ".join([
            group.get("name") or "",
            group.get("description") or "",
            group.get("activity") or "",
        ]).lower()
        return any(kw in text for kw in COMPETITOR_KEYWORDS)

    def _is_target_group(self, group: dict) -> bool:
        text = " ".join([group.get("name") or "", group.get("description") or ""]).lower()
        return any(kw in text for kw in TARGET_KEYWORDS)

    def _is_valid_group(self, group: dict) -> bool:
        members = group.get("members_count", 0)
        return MIN_MEMBERS <= members <= MAX_MEMBERS and group.get("is_closed", 1) == 0

    def _score_group(self, group: dict) -> int:
        score = 0
        name = (group.get("name") or "").lower()
        text = name + " " + (group.get("description") or "").lower()
        for kw in ["жк", "жител", "сосед", "жильц", "тсж"]:
            if kw in name:
                score += 15
        for kw in TARGET_KEYWORDS:
            if kw in text:
                score += 5
        members = group.get("members_count", 0)
        if 500 <= members <= 50_000:
            score += 20
        elif 100 <= members < 500:
            score += 5
        if "москв" in text:
            score += 10
        return min(score, 100)

    async def _remove_competitors(self, conn) -> int:
        rows = await (await conn.execute(
            "SELECT id, title FROM target_resources WHERE platform = 'vk'"
        )).fetchall()
        removed = 0
        for row_id, title in rows:
            if title and any(kw in title.lower() for kw in COMPETITOR_KEYWORDS):
                await conn.execute("DELETE FROM target_resources WHERE id = ?", (row_id,))
                logger.info(f"Discovery: удалён конкурент '{title}'")
                removed += 1
        await conn.commit()
        return removed

    async def _add_group_to_db(self, conn, group: dict, priority: int) -> bool:
        link = f"https://vk.com/club{group.get('id')}"
        members = group.get("members_count", 0)
        try:
            await conn.execute(
                """INSERT OR IGNORE INTO target_resources
                   (type, link, title, platform, status, is_active,
                    geo_tag, participants_count, is_high_priority, priority, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "vk_group", link, group.get("name", ""), "vk", "active", 1,
                    "Москва", members, 1 if priority >= 60 else 0, priority,
                    f"Авто-добавлено Discovery | участников: {members}",
                ),
            )
            await conn.commit()
            row = await (await conn.execute(
                "SELECT id FROM target_resources WHERE link = ?", (link,)
            )).fetchone()
            return row is not None
        except Exception as e:
            logger.error(f"_add_group_to_db {group.get('name')}: {e}")
            return False

    # ──────────────────────────────────────────
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ HUNT
    # ──────────────────────────────────────────

    def _check_geo(self, text: str) -> bool:
        return any(kw in (text or "").lower() for kw in self.geo_keywords)

    async def _analyze_intent(self, text: str) -> Dict:
        if not text or not text.strip():
            return {"is_lead": False, "intent": "", "hotness": 0, "context_summary": ""}
        try:
            from utils.yandex_ai_agents import call_spy_agent
            spy = await call_spy_agent(text)
            hotness = spy.get("hotness", 3)
            return {
                "is_lead": hotness >= 2,
                "intent": spy.get("recommendation", "")[:200] or "Запрос по перепланировке",
                "hotness": hotness,
                "context_summary": spy.get("recommendation", "")[:300],
                "recommendation": spy.get("recommendation", ""),
                "pain_level": spy.get("pain_level", min(hotness, 5)),
                "pain_stage": spy.get("pain_stage"),
            }
        except Exception:
            pass

        if not router_ai:
            return {
                "is_lead": "ищу" in text.lower(), "intent": "Поиск",
                "hotness": 3, "context_summary": "AI offline",
                "recommendation": "", "pain_level": 3,
            }

        prompt = (
            f"Проанализируй сообщение: {text}. "
            "Если это запрос услуги (дизайн/перепланировка) - is_lead: true. "
            "Выдай JSON: is_lead, intent, hotness (1-5), context_summary"
        )
        try:
            response = await router_ai.generate_response(prompt, model="kimi")
            out = json.loads(re.search(r'\{.*\}', response, re.DOTALL).group(0))
            out.setdefault("recommendation", out.get("context_summary", ""))
            out.setdefault("pain_level", min(out.get("hotness", 3), 5))
            return out
        except Exception:
            return {
                "is_lead": False, "intent": "error", "hotness": 0,
                "context_summary": "ошибка анализа", "recommendation": "", "pain_level": 3,
            }
