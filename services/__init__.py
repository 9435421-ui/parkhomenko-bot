"""
Сервисы бота
"""
<<<<<<< HEAD
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
=======
from .lead_service import lead_service, LeadService
from .vk_service import vk_service, VKService
from .competitor_spy import competitor_spy, CompetitorSpy, run_competitor_spy, run_geo_spy
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377

__all__ = [
    'lead_service', 'LeadService',
    'vk_service', 'VKService',
    'competitor_spy', 'CompetitorSpy', 'run_competitor_spy', 'run_geo_spy'
]
