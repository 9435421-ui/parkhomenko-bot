"""
vk_spy.py — автономный VK-шпион ТЕРИОН.

Работает БЕЗ:
  - Telethon / Telegram-сессии
  - базы данных
  - основного бота

Нужно только в .env:
  VK_TOKEN=vk1.a....
  BOT_TOKEN=...
  LEADS_GROUP_CHAT_ID=-100...
  THREAD_ID_HOT_LEADS=811        # топик «Горячие лиды» (опционально)
  SCOUT_VK_GROUPS=225569022,123456789,987654321
  VK_QUIZ_LINK=https://t.me/Parkhovenko_i_kompaniya_bot?start=quiz

Запуск:
  screen -S vk_spy
  cd /root/PARKHOMENKO_BOT
  python vk_spy.py
  Ctrl+A, D  — отсоединиться

Логи:
  tail -f vk_spy.log
"""

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp
from dotenv import load_dotenv

load_dotenv()

def validate_env_variables():
    """Проверка .env на наличие заглушек и обязательных переменных."""
    critical_vars = {
        "VK_TOKEN": os.getenv("VK_TOKEN", ""),
        "BOT_TOKEN": os.getenv("BOT_TOKEN", ""),
        "LEADS_GROUP_CHAT_ID": os.getenv("LEADS_GROUP_CHAT_ID", ""),
        "SCOUT_VK_GROUPS": os.getenv("SCOUT_VK_GROUPS", ""),
        "VK_SCAN_INTERVAL": os.getenv("VK_SCAN_INTERVAL", ""),
    }
    
    for var_name, value in critical_vars.items():
        if not value:
            print(f"❌ Ошибка конфигурации: {var_name} не задан в .env")
            sys.exit(1)
        
        # Проверка на заглушки
        if any(placeholder in str(value).lower() for placeholder in ["your_", "change_me", "id_here"]):
            print(f"❌ Ошибка конфигурации: {var_name} содержит заглушку: '{value}'. Исправьте .env")
            sys.exit(1)
    
    # Проверка числовых значений
    try:
        val = os.getenv("VK_SCAN_INTERVAL", "")
        if val:
            int(val)
    except ValueError:
        print(f"❌ Ошибка конфигурации: VK_SCAN_INTERVAL должен быть числом, получено: '{val}'")
        sys.exit(1)
    
    return True

# ─── Логирование ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("vk_spy.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("VKSpy")

# ─── Конфигурация ─────────────────────────────────────────────────────────────

VK_TOKEN           = os.getenv("VK_TOKEN", "")
BOT_TOKEN          = os.getenv("BOT_TOKEN", "")
LEADS_GROUP_CHAT_ID = os.getenv("LEADS_GROUP_CHAT_ID", "")
THREAD_ID_HOT_LEADS = os.getenv("THREAD_ID_HOT_LEADS", "")
VK_QUIZ_LINK       = os.getenv("VK_QUIZ_LINK", "https://t.me/Parkhovenko_i_kompaniya_bot?start=quiz")
JULIA_CONTACT      = os.getenv("JULIA_CONTACT", "@Parkhovenko_i_kompaniya_bot")
VK_API             = "5.199"

# Группы для парсинга из .env: SCOUT_VK_GROUPS=225569022,123456789
_raw_groups = os.getenv("SCOUT_VK_GROUPS", "")
VK_GROUPS: list[str] = [g.strip().lstrip("-") for g in _raw_groups.split(",") if g.strip()]

# Интервал между циклами сканирования (секунды)
SCAN_INTERVAL = int(os.getenv("VK_SCAN_INTERVAL", "1800"))  # 30 минут по умолчанию

# Файл для хранения уже обработанных ID (чтобы не дублировать лиды)
SEEN_FILE = Path("vk_spy_seen.json")

# ─── Ключевые слова ───────────────────────────────────────────────────────────

STOP_WORDS = [
    "продам", "сдам", "аренда", "куплю", "ищу квартиру",
    "риелтор", "агентство", "новостройка", "скидка", "акция",
    "подписывайтесь", "переходите по ссылке", "наш сайт",
    "оставьте заявку", "звоните нам", "специальное предложение",
]

HOT_TRIGGERS = [
    r"предписание\s*мжи",
    r"штраф\s+за\s+перепланировку",
    r"блокировка\s+сделки",
    r"узаконить\s+перепланировку",
    r"инспектор\s+мжи",
    r"согласовать\s+перепланировку",
    r"проект\s+перепланировки",
    r"заказать\s+проект",
    r"нужен\s+проект",
    r"кто\s+согласовывал",
    r"нужна\s+помощь.*перепланировк",
    r"перепланировк.*срочно",
]

TECHNICAL_TERMS = [
    r"перепланиров",
    r"согласовани",
    r"узакони",
    r"\bмжи\b",
    r"\bбти\b",
    r"акт\s+скрытых",
    r"снос\s+(стен|подоконн|блока)",
    r"объединен",
    r"нежилое\s+помещен",
    r"план\s+(квартир|помещен)",
    r"мокрая\s+зона",
    r"несущая\s+стена",
    r"демонтаж\s+стен",
    r"перенос\s+кухн",
]

COMMERCIAL_MARKERS = [
    r"сколько\s+стоит",
    r"\bцена\b",
    r"\bстоимость\b",
    r"к\s+кому\s+обратиться",
    r"посоветуйте\s+(компани|специалист|фирм)",
    r"заказать\s+проект",
    r"оформить\s+перепланировку",
    r"согласовал\w*",
    r"узаконил\w*",
    r"кто\s+делал",
    r"кто\s+помогал",
    r"порекомендуйте",
    r"подскажите\s+(компани|специалист)",
]

QUESTION_MARKERS = [
    r"\?\s*$",
    r"подскажите",
    r"помогите",
    r"как\s+(согласовать|узаконить|оформить|сделать)",
    r"кто\s+(согласовывал|оформлял|делал|заказывал|помогал)",
    r"есть\s+кто",
    r"посоветуйте",
    r"нужна\s+помощь",
    r"что\s+делать",
    r"с\s+чего\s+начать",
]


# ─── Фильтрация ───────────────────────────────────────────────────────────────

def _matches(text: str, patterns: list) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in patterns)

def _has_stop_word(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in STOP_WORDS)

def _count_links(text: str) -> int:
    return len(re.findall(r"https?://|vk\.com/|t\.me/", text))

def detect_lead(text: str) -> Optional[str]:
    """Возвращает 'hot', 'warm' или None."""
    if not text or len(text.strip()) < 15:
        return None
    if len(text) > 2000:
        return None
    if _has_stop_word(text):
        return None
    if _count_links(text) > 2:
        return None

    # Горячий триггер — безусловный лид
    if _matches(text, HOT_TRIGGERS):
        return "hot"

    has_tech     = _matches(text, TECHNICAL_TERMS)
    has_comm     = _matches(text, COMMERCIAL_MARKERS)
    has_question = _matches(text, QUESTION_MARKERS)

    # Для VK достаточно технического термина + вопроса/коммерческого маркера
    if has_tech and (has_comm or has_question):
        return "warm"

    # Или просто технический термин в вопросительном сообщении
    if has_tech and "?" in text:
        return "warm"

    return None


# ─── Хранилище просмотренных ID ───────────────────────────────────────────────

def load_seen() -> set:
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()

def save_seen(seen: set) -> None:
    try:
        # Храним только последние 10000 ID чтобы файл не рос бесконечно
        trimmed = list(seen)[-10000:]
        SEEN_FILE.write_text(json.dumps(trimmed), encoding="utf-8")
    except Exception as e:
        logger.warning("Не удалось сохранить seen: %s", e)


# ─── VK API ───────────────────────────────────────────────────────────────────

async def vk_get(session: aiohttp.ClientSession, method: str, params: dict) -> Optional[dict]:
    """Выполняет запрос к VK API."""
    params.update({"access_token": VK_TOKEN, "v": VK_API})
    try:
        async with session.get(
            f"https://api.vk.com/method/{method}",
            params=params,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            data = await resp.json()
            if "error" in data:
                err = data["error"]
                logger.warning("VK API error [%s] %s: %s", method, err.get("error_code"), err.get("error_msg"))
                return None
            return data.get("response")
    except asyncio.TimeoutError:
        logger.warning("Timeout: VK API %s", method)
    except Exception as e:
        logger.error("VK API exception [%s]: %s", method, e)
    return None


async def get_vk_user(session: aiohttp.ClientSession, user_id: int) -> dict:
    """Получает имя и ссылку VK-пользователя."""
    try:
        resp = await vk_get(session, "users.get", {
            "user_ids": user_id,
            "fields": "screen_name"
        })
        if resp and len(resp) > 0:
            u = resp[0]
            name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
            screen = u.get("screen_name", f"id{user_id}")
            return {"name": name, "url": f"https://vk.com/{screen}"}
    except Exception:
        pass
    return {"name": f"id{user_id}", "url": f"https://vk.com/id{user_id}"}


async def fetch_wall(session: aiohttp.ClientSession, group_id: str, count: int = 50) -> list:
    """Получает посты со стены группы."""
    resp = await vk_get(session, "wall.get", {
        "owner_id": f"-{group_id}",
        "count": count,
        "filter": "all",
    })
    if not resp:
        return []
    return resp.get("items", [])


async def fetch_comments(
    session: aiohttp.ClientSession,
    group_id: str,
    post_id: int,
    count: int = 100,
) -> list:
    """Получает комментарии под постом."""
    resp = await vk_get(session, "wall.getComments", {
        "owner_id": f"-{group_id}",
        "post_id": post_id,
        "count": count,
        "sort": "desc",      # сначала новые
        "need_likes": 0,
    })
    if not resp:
        return []
    return resp.get("items", [])


# ─── Отправка в Telegram ──────────────────────────────────────────────────────

async def send_lead_card(session: aiohttp.ClientSession, lead: dict) -> bool:
    """Отправляет карточку лида в рабочую группу Telegram."""
    if not BOT_TOKEN or not LEADS_GROUP_CHAT_ID:
        logger.warning("BOT_TOKEN или LEADS_GROUP_CHAT_ID не заданы — карточка не отправлена")
        return False

    lead_type   = lead.get("lead_type", "warm")
    text        = lead.get("text", "")
    source_url  = lead.get("source_url", "")
    author_name = lead.get("author_name", "Неизвестно")
    author_url  = lead.get("author_url", "")
    group_id    = lead.get("group_id", "")
    post_id     = lead.get("post_id", "")
    source_type = lead.get("source_type", "post")   # post | comment

    icon = "🔥" if lead_type == "hot" else "🎯"
    type_label = "ГОРЯЧИЙ ЛИД" if lead_type == "hot" else "Тёплый лид"
    src_label  = "комментарий" if source_type == "comment" else "пост"

    # Ссылка на источник
    if source_url:
        post_link = source_url
    elif group_id and post_id:
        post_link = f"https://vk.com/wall-{group_id}_{post_id}"
    else:
        post_link = "https://vk.com"

    author_line = (
        f'<a href="{author_url}">{author_name}</a>'
        if author_url else author_name
    )

    msg = (
        f"{icon} <b>{type_label} — VK</b>\n"
        f"\n"
        f"👤 <b>Автор:</b> {author_line}\n"
        f"📍 <b>Источник:</b> <a href='{post_link}'>открыть {src_label}</a>\n"
        f"\n"
        f"💬 <b>Сообщение:</b>\n"
        f"{text[:600]}{'...' if len(text) > 600 else ''}\n"
        f"\n"
        f"🔗 <a href='{VK_QUIZ_LINK}'>Отправить квиз</a> | {JULIA_CONTACT}"
    )

    payload: dict = {
        "chat_id": LEADS_GROUP_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if THREAD_ID_HOT_LEADS and lead_type == "hot":
        payload["message_thread_id"] = int(THREAD_ID_HOT_LEADS)
    elif THREAD_ID_HOT_LEADS:
        payload["message_thread_id"] = int(THREAD_ID_HOT_LEADS)

    try:
        async with session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status == 200:
                return True
            else:
                body = await resp.text()
                logger.error("Telegram sendMessage error %s: %s", resp.status, body[:200])
    except Exception as e:
        logger.error("Telegram send exception: %s", e)

    return False


# ─── Основной цикл сканирования ───────────────────────────────────────────────

async def scan_group(
    session: aiohttp.ClientSession,
    group_id: str,
    seen: set,
) -> int:
    """Сканирует одну VK-группу. Возвращает количество новых лидов."""
    found = 0
    logger.info("🔍 Сканирую группу %s...", group_id)

    posts = await fetch_wall(session, group_id, count=30)
    if not posts:
        logger.info("  Группа %s: постов не получено", group_id)
        return 0

    for post in posts:
        post_id  = post.get("id")
        from_id  = post.get("from_id", 0)
        post_text = post.get("text", "")
        post_key  = f"post_{group_id}_{post_id}"

        # Проверяем сам пост (только от реальных пользователей, не от группы)
        if from_id > 0 and post_key not in seen:
            lead_type = detect_lead(post_text)
            if lead_type:
                seen.add(post_key)
                user = await get_vk_user(session, from_id)
                lead = {
                    "lead_type":   lead_type,
                    "text":        post_text,
                    "source_url":  f"https://vk.com/wall-{group_id}_{post_id}",
                    "author_name": user["name"],
                    "author_url":  user["url"],
                    "group_id":    group_id,
                    "post_id":     post_id,
                    "source_type": "post",
                }
                ok = await send_lead_card(session, lead)
                if ok:
                    found += 1
                    logger.info("  ✅ Лид из поста %s (%s)", post_id, lead_type)
                await asyncio.sleep(0.5)

        # Проверяем комментарии под постом
        comments = await fetch_comments(session, group_id, post_id, count=50)
        await asyncio.sleep(0.3)   # пауза между запросами

        for comment in comments:
            c_id      = comment.get("id")
            c_from_id = comment.get("from_id", 0)
            c_text    = comment.get("text", "")
            c_key     = f"comment_{group_id}_{post_id}_{c_id}"

            # Только реальные пользователи
            if c_from_id <= 0 or c_key in seen:
                continue

            lead_type = detect_lead(c_text)
            if lead_type:
                seen.add(c_key)
                user = await get_vk_user(session, c_from_id)
                lead = {
                    "lead_type":   lead_type,
                    "text":        c_text,
                    "source_url":  f"https://vk.com/wall-{group_id}_{post_id}?reply={c_id}",
                    "author_name": user["name"],
                    "author_url":  user["url"],
                    "group_id":    group_id,
                    "post_id":     post_id,
                    "source_type": "comment",
                }
                ok = await send_lead_card(session, lead)
                if ok:
                    found += 1
                    logger.info("  ✅ Лид из комментария %s (пост %s) (%s)", c_id, post_id, lead_type)
                await asyncio.sleep(0.5)

    logger.info("  Группа %s: %d новых лидов", group_id, found)
    return found


async def run_scan_cycle(seen: set) -> int:
    """Один полный цикл по всем группам."""
    if not VK_GROUPS:
        logger.error(
            "❌ SCOUT_VK_GROUPS не задан в .env!\n"
            "   Добавьте: SCOUT_VK_GROUPS=225569022,123456789"
        )
        return 0

    total = 0
    async with aiohttp.ClientSession() as session:
        for group_id in VK_GROUPS:
            try:
                found = await scan_group(session, group_id, seen)
                total += found
            except Exception as e:
                logger.error("Ошибка сканирования группы %s: %s", group_id, e)
            # Пауза между группами — защита от rate limit
            await asyncio.sleep(2)

    save_seen(seen)
    return total


async def send_startup_message() -> None:
    """Уведомляет рабочую группу о старте шпиона."""
    if not BOT_TOKEN or not LEADS_GROUP_CHAT_ID:
        return
    groups_str = ", ".join(f"vk.com/club{g}" for g in VK_GROUPS) or "не настроены"
    msg = (
        f"🕵️ <b>VK-шпион ТЕРИОН запущен</b>\n\n"
        f"📘 Группы: {groups_str}\n"
        f"⏱ Интервал сканирования: {SCAN_INTERVAL // 60} мин\n"
        f"🔑 Ключевых слов (горячие): {len(HOT_TRIGGERS)}\n"
        f"🔑 Технических терминов: {len(TECHNICAL_TERMS)}"
    )
    payload = {
        "chat_id": LEADS_GROUP_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
    }
    if THREAD_ID_HOT_LEADS:
        payload["message_thread_id"] = int(THREAD_ID_HOT_LEADS)
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            )
    except Exception as e:
        logger.warning("Не удалось отправить стартовое сообщение: %s", e)


# ─── Проверка конфигурации ────────────────────────────────────────────────────

def check_config() -> bool:
    ok = True
    if not VK_TOKEN:
        logger.error("❌ VK_TOKEN не задан в .env")
        ok = False
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не задан в .env")
        ok = False
    if not LEADS_GROUP_CHAT_ID:
        logger.error("❌ LEADS_GROUP_CHAT_ID не задан в .env")
        ok = False
    if not VK_GROUPS:
        logger.error("❌ SCOUT_VK_GROUPS не задан в .env (пример: SCOUT_VK_GROUPS=225569022,123456789)")
        ok = False
    return ok


# ─── Точка входа ──────────────────────────────────────────────────────────────

async def main() -> None:
    logger.info("=" * 55)
    logger.info("  VK-шпион ТЕРИОН — старт")
    logger.info("=" * 55)

    # Проверка конфигурации перед запуском
    if not validate_env_variables():
        logger.error("🚨 Ошибка конфигурации: исправьте .env")
        return

    if not check_config():
        logger.error("Исправьте .env и перезапустите.")
        return

    logger.info("📘 Группы для парсинга: %s", VK_GROUPS)
    logger.info("⏱  Интервал: %d сек (%d мин)", SCAN_INTERVAL, SCAN_INTERVAL // 60)

    seen = load_seen()
    logger.info("💾 Загружено %d просмотренных записей", len(seen))

    await send_startup_message()

    cycle = 0
    while True:
        cycle += 1
        start_ts = time.time()
        logger.info("─── Цикл #%d ───────────────────────────────────", cycle)

        try:
            total_leads = await run_scan_cycle(seen)
            elapsed = int(time.time() - start_ts)
            logger.info(
                "✅ Цикл #%d завершён за %d сек | Найдено лидов: %d | Seen: %d",
                cycle, elapsed, total_leads, len(seen)
            )
        except Exception as e:
            logger.error("❌ Ошибка в цикле #%d: %s", cycle, e)

        logger.info("💤 Следующий скан через %d мин...", SCAN_INTERVAL // 60)
        await asyncio.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 VK-шпион остановлен вручную.")
