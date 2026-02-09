"""
Сервисы бота
"""
from .lead_service import lead_service, LeadService
from .vk_service import vk_service, VKService
from .competitor_spy import competitor_spy, CompetitorSpy, run_competitor_spy, run_geo_spy

__all__ = [
    'lead_service', 'LeadService',
    'vk_service', 'VKService',
    'competitor_spy', 'CompetitorSpy', 'run_competitor_spy', 'run_geo_spy'
]
