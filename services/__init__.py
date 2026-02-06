"""
Сервисы бота
"""
from .lead_service import send_lead_to_admin_group, send_contact_to_logs
from .vk_service import vk_service

__all__ = ['send_lead_to_admin_group', 'send_contact_to_logs', 'vk_service']
