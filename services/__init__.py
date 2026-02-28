"""
Сервисы бота
"""
# Импорт lead_service и VKService (если файлы существуют)
try:
    from .lead_service import lead_service, LeadService
except ImportError:
    lead_service = None
    LeadService = None

try:
    from .vk_service import vk_service, VKService
except ImportError:
    vk_service = None
    VKService = None

__all__ = ['lead_service', 'LeadService', 'vk_service', 'VKService']
