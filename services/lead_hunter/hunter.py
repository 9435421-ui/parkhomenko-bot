import logging
from .discovery import Discovery
from .analyzer import LeadAnalyzer
from .outreach import Outreach
from services.scout_parser import ScoutParser

logger = logging.getLogger(__name__)

class LeadHunter:
    """Автономный поиск и привлечение клиентов (Lead Hunter)"""
    
    def __init__(self):
        self.discovery = Discovery()
        self.analyzer = LeadAnalyzer()
        self.outreach = Outreach()
        self.parser = ScoutParser() # Используем существующий парсер как базу
        
    async def hunt(self):
        """Полный цикл: поиск → анализ → привлечение"""
        logger.info("🏹 LeadHunter: начало охоты за лидами...")
        
        # 1. Парсинг (используем существующую логику)
        tg_posts = await self.parser.parse_telegram()
        vk_posts = await self.parser.parse_vk()
        
        all_posts = tg_posts + vk_posts
        
        for post in all_posts:
            # 2. Анализ
            score = await self.analyzer.analyze_post(post.text)
            
            if score > 0.7:
                logger.info(f"🎯 Найден горячий лид! Score: {score}")
                # 3. Привлечение
                message = self.parser.generate_outreach_message(post.source_type)
                await self.outreach.send_offer(post.source_type, post.source_id, message)
        
        logger.info(f"🏹 LeadHunter: охота завершена. Обработано {len(all_posts)} постов.")
