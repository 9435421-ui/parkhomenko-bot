"""
scout_discovery.py — Автоматический поиск целевых VK-пабликов для ГЕОРИС
Синхронная версия (telebot + schedule + sqlite3)
"""

import os
import time
import sqlite3
import logging
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

VK_API_BASE = "https://api.vk.com/method"
VK_API_VERSION = "5.131"

DB_PATH = os.getenv("DB_PATH", "parkhomenko_bot.db")
VK_TOKEN = os.getenv("VK_TOKEN", "")

SEARCH_QUERIES = [
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

COMPETITOR_KEYWORDS = [
    "перепланировк", "согласован", "дизайн-проект", "дизайн проект",
    "архитектурное бюро", "проектирование квартир", "технический план",
    "кадастровый инженер", "бти услуги", "риэлтор",
]

TARGET_KEYWORDS = [
    "жк", "жител", "сосед", "двор", "подъезд",
    "жильц", "тсж", "район", "микрорайон", "новостройк",
    "квартал", "корпус", "управляющ",
]

MIN_MEMBERS = 100
MAX_MEMBERS = 500_000
RESULTS_PER_QUERY = 20


def vk_search_groups(query: str) -> list:
    params = {
        "q": query, "type": "group", "country_id": 1, "city_id": 1,
        "count": RESULTS_PER_QUERY,
        "fields": "members_count,description,status,activity",
        "access_token": VK_TOKEN, "v": VK_API_VERSION,
    }
    try:
        resp = requests.get(f"{VK_API_BASE}/groups.search", params=params, timeout=15)
        data = resp.json()
        if "error" in data:
            logger.warning(f"VK API error '{query}': {data['error']}")
            return []
        items = data.get("response", {}).get("items", [])
        logger.info(f"Запрос '{query}': {len(items)} групп")
        return items
    except Exception as e:
        logger.error(f"Ошибка VK search '{query}': {e}")
        return []


def is_competitor(group: dict) -> bool:
    text = " ".join([
        group.get("name") or "",
        group.get("description") or "",
        group.get("activity") or "",
    ]).lower()
    return any(kw in text for kw in COMPETITOR_KEYWORDS)


def is_target(group: dict) -> bool:
    text = " ".join([group.get("name") or "", group.get("description") or ""]).lower()
    return any(kw in text for kw in TARGET_KEYWORDS)


def is_valid(group: dict) -> bool:
    members = group.get("members_count", 0)
    return MIN_MEMBERS <= members <= MAX_MEMBERS and group.get("is_closed", 1) == 0


def score_group(group: dict) -> int:
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


def get_existing_links(conn: sqlite3.Connection) -> set:
    cur = conn.execute("SELECT link FROM target_resources")
    return {row[0] for row in cur.fetchall()}


def remove_competitor_groups(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        "SELECT id, title FROM target_resources WHERE platform = 'vk'"
    ).fetchall()
    removed = 0
    for row_id, title in rows:
        if title and any(kw in title.lower() for kw in COMPETITOR_KEYWORDS):
            conn.execute("DELETE FROM target_resources WHERE id = ?", (row_id,))
            logger.info(f"Удалён конкурент: {title}")
            removed += 1
    conn.commit()
    return removed


def add_group(conn: sqlite3.Connection, group: dict, priority: int) -> bool:
    link = f"https://vk.com/club{group.get('id')}"
    members = group.get("members_count", 0)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO target_resources
               (type, link, title, platform, status, is_active,
                geo_tag, participants_count, is_high_priority, priority, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "vk_group", link, group.get("name", ""), "vk", "active", 1,
                "Москва", members, 1 if priority >= 60 else 0, priority,
                f"Авто-добавлено scout_discovery | участников: {members}",
            ),
        )
        conn.commit()
        return conn.execute(
            "SELECT id FROM target_resources WHERE link = ?", (link,)
        ).fetchone() is not None
    except Exception as e:
        logger.error(f"Ошибка добавления {group.get('name')}: {e}")
        return False


def run_discovery() -> dict:
    """Вызывается из планировщика. Возвращает статистику."""
    stats = {"removed": 0, "found": 0, "added": 0,
             "skipped_competitor": 0, "skipped_invalid": 0, "skipped_exists": 0}

    if not VK_TOKEN:
        logger.error("VK_TOKEN не задан")
        return stats

    conn = sqlite3.connect(DB_PATH)
    try:
        stats["removed"] = remove_competitor_groups(conn)
        existing = get_existing_links(conn)

        all_groups = {}
        for query in SEARCH_QUERIES:
            time.sleep(0.4)
            for g in vk_search_groups(query):
                gid = g.get("id")
                if gid and gid not in all_groups:
                    all_groups[gid] = g

        stats["found"] = len(all_groups)

        for group in all_groups.values():
            link = f"https://vk.com/club{group.get('id')}"
            if link in existing:
                stats["skipped_exists"] += 1
            elif is_competitor(group):
                stats["skipped_competitor"] += 1
            elif not is_valid(group) or not is_target(group):
                stats["skipped_invalid"] += 1
            else:
                priority = score_group(group)
                if add_group(conn, group, priority):
                    stats["added"] += 1
                    logger.info(f"✅ {group.get('name')} | {group.get('members_count')} уч. | приоритет: {priority}")
                else:
                    stats["skipped_exists"] += 1
    finally:
        conn.close()

    logger.info(f"Discovery: удалено {stats['removed']}, добавлено {stats['added']} из {stats['found']}")
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("🔍 Запуск Discovery...\n")
    r = run_discovery()
    print(f"\n📊 Результат:")
    print(f"  🗑  Удалено конкурентов:  {r['removed']}")
    print(f"  🔎 Найдено групп:         {r['found']}")
    print(f"  ✅ Добавлено новых:       {r['added']}")
    print(f"  ❌ Конкурент (пропущен): {r['skipped_competitor']}")
    print(f"  ⚠️  Размер/тип (пропущен): {r['skipped_invalid']}")
    print(f"  ♻️  Уже в БД:             {r['skipped_exists']}")
