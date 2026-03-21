"""
VK Token Manager — сервис мониторинга и обновления VK токена
Расположение: /root/PARKHOMENKO_BOT/services/vk_token_manager.py
"""

import os
import logging
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── Константы ────────────────────────────────────────────────────────────────
VK_API_VERSION = "5.131"
CHECK_INTERVAL_HOURS = 6        # Проверка каждые 6 часов
WARN_DAYS_BEFORE = 3            # Предупреждение за 3 дня до истечения

# ── Ссылка для получения нового токена (Implicit Flow) ────────────────────────
# VK_APP_ID берётся из .env — это ID вашего VK приложения
# Если приложения нет — создать на https://vk.com/editapp?act=create
def get_refresh_url() -> str:
    app_id = os.getenv("VK_APP_ID", "")
    redirect = "https://oauth.vk.com/blank.html"
    scope = "wall,photos,groups,offline"   # offline = бессрочный токен!
    return (
        f"https://oauth.vk.com/authorize?"
        f"client_id={app_id}"
        f"&display=page"
        f"&redirect_uri={redirect}"
        f"&scope={scope}"
        f"&response_type=token"
        f"&v={VK_API_VERSION}"
    )


class VKTokenManager:
    """
    Менеджер VK токена.
    
    Использование в APScheduler (в run_content_bot.py):
    
        from services.vk_token_manager import VKTokenManager
        vk_manager = VKTokenManager(bot=bot)
        scheduler.add_job(vk_manager.check_token, 'interval', hours=6)
    """

    def __init__(self, bot=None):
        self.bot = bot                          # aiogram Bot instance для уведомлений
        self.admin_id = int(os.getenv("ADMIN_ID", "0"))
        self.admin_group_id = os.getenv("ADMIN_GROUP_ID", "")
        self._last_check: Optional[datetime] = None
        self._token_valid: bool = True

    # ── Публичный метод: запустить проверку ───────────────────────────────────
    async def check_token(self) -> bool:
        """
        Основной метод — вызывается по расписанию.
        Возвращает True если токен валиден.
        """
        token = os.getenv("VK_TOKEN", "")
        if not token:
            logger.error("❌ VK_TOKEN отсутствует в .env")
            await self._notify_admin("❌ *VK_TOKEN отсутствует* в .env файле!\nШпион не работает.")
            return False

        logger.info("🔍 Проверяем VK токен...")
        self._last_check = datetime.now()

        is_valid, expire_info = await self._verify_token(token)

        if not is_valid:
            logger.warning("⚠️ VK токен недействителен или истёк!")
            await self._notify_token_expired()
            self._token_valid = False
            return False

        self._token_valid = True

        # Предупреждение если токен истекает скоро
        if expire_info and expire_info < timedelta(days=WARN_DAYS_BEFORE):
            days_left = expire_info.days
            logger.warning(f"⚠️ VK токен истекает через {days_left} дней!")
            await self._notify_token_expiring_soon(days_left)
        else:
            logger.info("✅ VK токен валиден")

        return True

    # ── Проверка токена через VK API ──────────────────────────────────────────
    async def _verify_token(self, token: str) -> tuple[bool, Optional[timedelta]]:
        """
        Проверяет токен через users.get.
        Возвращает (is_valid, time_to_expire).
        time_to_expire = None если токен бессрочный (offline scope).
        """
        url = "https://api.vk.com/method/users.get"
        params = {
            "access_token": token,
            "v": VK_API_VERSION
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()

                    if "error" in data:
                        error_code = data["error"].get("error_code", 0)
                        error_msg = data["error"].get("error_msg", "")
                        logger.error(f"VK API error {error_code}: {error_msg}")

                        # Коды ошибок авторизации
                        if error_code in (5, 27, 28):
                            return False, None
                        # Другие ошибки — токен может быть валиден
                        return True, None

                    # Токен работает
                    # VK не возвращает expire_time напрямую через users.get
                    # Используем secure.checkToken если есть app_secret
                    expire = await self._check_token_expiry(token)
                    return True, expire

        except asyncio.TimeoutError:
            logger.error("❌ Таймаут при проверке VK токена")
            return True, None  # Не знаем — считаем валидным
        except Exception as e:
            logger.error(f"❌ Ошибка проверки VK токена: {e}")
            return True, None

    async def _check_token_expiry(self, token: str) -> Optional[timedelta]:
        """
        Пытается определить срок жизни токена.
        Если токен получен с scope=offline — он бессрочный, возвращаем None.
        """
        # Проверяем через account.getAppPermissions
        url = "https://api.vk.com/method/account.getAppPermissions"
        params = {
            "access_token": token,
            "v": VK_API_VERSION
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    if "response" in data:
                        permissions = data["response"]
                        # Бит 65536 = offline (бессрочный)
                        if permissions & 65536:
                            logger.info("✅ Токен бессрочный (offline scope)")
                            return None
                        else:
                            # Токен временный — не знаем точный срок
                            # Предупреждаем сразу
                            logger.warning("⚠️ Токен без offline scope — может истечь!")
                            return timedelta(days=1)  # Считаем что скоро истечёт
        except Exception:
            pass
        return None

    # ── Уведомления в Telegram ────────────────────────────────────────────────
    async def _notify_admin(self, message: str):
        """Отправляет уведомление администратору."""
        if not self.bot or not self.admin_id:
            logger.warning(f"Уведомление (нет бота): {message}")
            return
        try:
            await self.bot.send_message(
                chat_id=self.admin_id,
                text=message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление: {e}")

    async def _notify_token_expired(self):
        """Уведомление об истёкшем токене с инструкцией."""
        refresh_url = get_refresh_url()
        app_id = os.getenv("VK_APP_ID", "НЕ ЗАДАН")

        message = (
            "🚨 *VK ТОКЕН ИСТЁК!*\n\n"
            "Шпион и публикации в VK не работают.\n\n"
            "📋 *Как получить новый токен:*\n\n"
            "1️⃣ Если `VK_APP_ID` задан — открой ссылку ниже в браузере:\n"
            f"`{refresh_url}`\n\n"
            "2️⃣ Войди в VK и разреши доступ\n\n"
            "3️⃣ Из адресной строки скопируй `access_token=...` (до `&`)\n\n"
            "4️⃣ Обнови `.env`:\n"
            "`VK_TOKEN=новый_токен`\n\n"
            "5️⃣ Перезапусти сервис:\n"
            "`systemctl restart content-bot.service`\n\n"
            "💡 *Совет:* Добавь `scope=offline` — токен станет бессрочным!\n\n"
            f"VK_APP_ID сейчас: `{app_id}`"
        )
        await self._notify_admin(message)

    async def _notify_token_expiring_soon(self, days_left: int):
        """Предупреждение о скором истечении токена."""
        message = (
            f"⚠️ *VK токен истекает через {days_left} дн.*\n\n"
            "Пора обновить, пока шпион ещё работает.\n"
            "Напиши /vk_token_refresh для инструкции."
        )
        await self._notify_admin(message)

    # ── Статус ────────────────────────────────────────────────────────────────
    def get_status(self) -> dict:
        """Возвращает текущий статус токена."""
        return {
            "valid": self._token_valid,
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "token_preview": os.getenv("VK_TOKEN", "")[:20] + "..." if os.getenv("VK_TOKEN") else "отсутствует"
        }


# ── Быстрая проверка из командной строки ─────────────────────────────────────
async def _cli_check():
    """python3 services/vk_token_manager.py — проверить токен вручную"""
    from dotenv import load_dotenv
    load_dotenv()

    manager = VKTokenManager()
    print("🔍 Проверяем VK токен...")
    is_valid = await manager.check_token()

    status = manager.get_status()
    print(f"\n📊 Статус:")
    print(f"  Токен: {status['token_preview']}")
    print(f"  Валиден: {'✅ Да' if is_valid else '❌ Нет'}")
    print(f"  Проверен: {status['last_check']}")

    if not is_valid:
        print(f"\n🔗 Ссылка для обновления:")
        print(f"  {get_refresh_url()}")


if __name__ == "__main__":
    asyncio.run(_cli_check())
