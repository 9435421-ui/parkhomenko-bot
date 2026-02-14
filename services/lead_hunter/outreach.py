import logging
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class Outreach:
    """Отправка предложений и взаимодействие с потенциальными клиентами"""
    
    def __init__(self):
        # Настройка бизнес-часов (с 9:00 до 21:00)
        self.work_start = 9
        self.work_end = 21

    def is_work_hours(self) -> bool:
        """Проверка, можно ли сейчас писать клиенту"""
        current_hour = datetime.now().hour
        return self.work_start <= current_hour < self.work_end

    async def send_offer(self, platform: str, target_id: str, message: str):
        """Отправка сообщения/комментария с учетом времени"""
        logger.info(f"✉️ Outreach: отправка предложения на {platform} для {target_id}...")
        
        if self.is_work_hours():
            logger.info(f"🚀 Рабочее время. Отправляем оффер клиенту {target_id}")
            # Логика отправки через API (Telegram/VK)
            return True
        else:
            logger.info(f"🌙 Ночной режим. Сохраняем лид {target_id} до утра.")
            # Сохраняем лид для отправки утром
            await self.notify_admin_about_lead(platform, target_id, message)
            return False

    async def send_proposal(self, client_id: str, text: str):
        """Отправка предложения с учетом времени"""
        if self.is_work_hours():
            logger.info(f"🚀 Рабочее время. Отправляем оффер клиенту {client_id}")
            # Здесь будет вызов bot.send_message клиенту
        else:
            logger.info(f"🌙 Ночной режим. Сохраняем лид {client_id} до утра.")
            # Здесь логика сохранения в базу или отправка ВАМ на одобрение
            await self.notify_admin_about_lead(client_id, text)

    async def notify_admin_about_lead(self, platform: str, client_id: str, message: str = ""):
        """Уведомление о ночном лиде для ручной проверки"""
        logger.info(f"🔔 Ночной лид: {platform} -> {client_id}")
        # TODO: Отправить уведомление в админ-чат
        # Здесь можно добавить отправку в LEADS_GROUP_CHAT_ID
        pass
