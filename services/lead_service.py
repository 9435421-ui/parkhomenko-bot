"""
Сервис для работы с лидами (отправка в группу Telegram)
"""
import os
from datetime import datetime
from typing import Dict, Optional
from aiogram import Bot


class LeadService:
    """Сервис для отправки лидов в группу Telegram"""
    
    def __init__(self):
        self.leads_group_id = int(os.getenv("LEADS_GROUP_CHAT_ID", "0"))
        self.thread_kvartiry = int(os.getenv("THREAD_ID_KVARTIRY", "0"))
        self.thread_kommercia = int(os.getenv("THREAD_ID_KOMMERCIA", "0"))
        self.thread_doma = int(os.getenv("THREAD_ID_DOMA", "0"))
    
    async def send_lead_to_group(
        self,
        bot: Bot,
        lead_data: Dict,
        user_id: int
    ) -> bool:
        """
        Отправка лида в группу Telegram
        
        Args:
            bot: Экземпляр бота
            lead_data: Данные лида
            user_id: ID пользователя
        
        Returns:
            bool: Успешность отправки
        """
        # Определяем топик по типу объекта
        object_type = lead_data.get('object_type', '')
        
        if object_type == "Квартира":
            thread_id = self.thread_kvartiry
        elif object_type == "Коммерция":
            thread_id = self.thread_kommercia
        elif object_type == "Дом":
            thread_id = self.thread_doma
        else:
            thread_id = None
        
        # Формируем текст лида
        lead_text = self._format_lead_text(lead_data, user_id)
        
        try:
            if thread_id and thread_id > 0:
                await bot.send_message(
                    chat_id=self.leads_group_id,
                    text=lead_text,
                    message_thread_id=thread_id,
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    chat_id=self.leads_group_id,
                    text=lead_text,
                    parse_mode="HTML"
                )
            
            return True
        except Exception as e:
            print(f"❌ Ошибка отправки лида: {e}")
            return False
    
    def _format_lead_text(self, lead_data: Dict, user_id: int) -> str:
        """Форматирование текста лида"""
        
        floor_info = ""
        if lead_data.get('floor_info'):
            floor_info = f"🏢 Этаж: {lead_data['floor_info']}"
        
        return f"""
📋 <b>Новая заявка на перепланировку</b>

👤 <b>Имя:</b> {lead_data.get('name', 'не указано')}
📞 <b>Телефон (TG):</b> {lead_data.get('phone', 'не указан')}
📪 <b>Доп. контакт:</b> {lead_data.get('extra_contact') or 'не указан'}

🏠 <b>Тип объекта:</b> {lead_data.get('object_type', 'не выбран')}
🏙️ <b>Город:</b> {lead_data.get('city', 'не указан')}
{floor_info}

🔧 <b>Статус:</b> {lead_data.get('remodeling_status', 'не указан')}
🛠️ <b>Что хочет изменить:</b>
{lead_data.get('change_plan', 'не указано')}

📄 <b>Статус БТИ:</b> {lead_data.get('bti_status', 'не указан')}

🕐 <b>Время:</b> {datetime.now().strftime("%d.%m.%Y %H:%M")}
👤 <b>User ID:</b> <code>{user_id}</code>
        """.strip()
    
    async def send_minimal_lead(
        self,
        bot: Bot,
        user_id: int,
        name: str,
        phone: str
    ) -> bool:
        """
        Отправка минимального лида (только контакт получен)
        
        Args:
            bot: Экземпляр бота
            user_id: ID пользователя
            name: Имя
            phone: Телефон
        
        Returns:
            bool: Успешность отправки
        """
        text = f"""
🆕 <b>НОВЫЙ КОНТАКТ</b>

👤 <b>Имя:</b> {name}
📞 <b>Телефон:</b> {phone}
👤 <b>User ID:</b> <code>{user_id}</code>

🕐 <b>Время:</b> {datetime.now().strftime("%d.%m.%Y %H:%M")}
ℹ️ <b>Статус:</b> контакт получен, тип объекта и заявка ещё не оформлены
        """.strip()
        
        try:
            await bot.send_message(
                chat_id=self.leads_group_id,
                text=text,
                parse_mode="HTML"
            )
            return True
        except Exception as e:
            print(f"❌ Ошибка отправки минимального лида: {e}")
            return False


# Singleton instance
lead_service = LeadService()
