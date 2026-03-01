"""
HunterDatabase - база данных для дедупликации лидов
Предотвращает повторную отправку сообщений одним и тем же людям
"""
import aiosqlite
import logging
import os
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class HunterDatabase:
    """Класс для работы с базой данных потенциальных лидов"""
    
    def __init__(self, db_path: str):
        """
        Инициализация базы данных
        
        Args:
            db_path: Путь к файлу базы данных SQLite
        """
        self.db_path = str(Path(db_path).resolve())
        self.conn: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """
        Подключение к базе данных и создание таблицы leads
        
        Создает таблицу для хранения URL лидов с целью дедупликации.
        Сохраняет соединение в self.conn для последующего использования.
        """
        # Создаем директорию, если её нет
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Подключаемся к базе данных (без context manager, чтобы сохранить соединение)
        self.conn = await aiosqlite.connect(self.db_path, timeout=30.0)
        self.conn.row_factory = aiosqlite.Row
        
        # Создаем таблицу для хранения лидов
        async with self.conn.cursor() as cursor:
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS leads (
                    url TEXT PRIMARY KEY,
                    content TEXT,
                    intent TEXT,
                    hotness INTEGER DEFAULT 3,
                    geo TEXT,
                    context_summary TEXT,
                    pain_stage TEXT,
                    priority_score INTEGER DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await self.conn.commit()
        
        logger.info(f"✅ Подключено к базе данных потенциальных лидов: {self.db_path}")
    
    async def save_lead(self, lead_data: Dict) -> bool:
        """
        Сохраняет лид в базу данных для дедупликации
        
        Args:
            lead_data: Словарь с данными лида:
                - url: URL поста (обязательно, используется как PRIMARY KEY)
                - content: Текст сообщения
                - intent: Намерение клиента
                - hotness: Уровень "горячести" (1-5)
                - geo: Географическая метка
                - context_summary: Краткое описание контекста
                - pain_stage: Стадия боли клиента (ST-1, ST-2, ST-3, ST-4)
                - priority_score: Приоритетный балл (0-10)
        
        Returns:
            True если лид новый и успешно сохранен, False если это дубликат
        """
        url = lead_data.get('url')
        if not url:
            logger.warning("Попытка сохранить лид без URL - пропуск")
            return False
        
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute('''
                    INSERT INTO leads (
                        url, content, intent, hotness, geo, 
                        context_summary, pain_stage, priority_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    url,
                    lead_data.get('content', '')[:2000],  # Ограничение длины
                    lead_data.get('intent', ''),
                    lead_data.get('hotness', 3),
                    lead_data.get('geo', 'Не указано'),
                    lead_data.get('context_summary', ''),
                    lead_data.get('pain_stage', 'ST-1'),
                    lead_data.get('priority_score', 0)
                ))
                await self.conn.commit()
                logger.debug(f"✅ Новый лид сохранен: {url[:50]}...")
                return True
        except aiosqlite.IntegrityError:
            # Дубликат - URL уже существует в базе
            logger.debug(f"⏭️ Дубликат лида пропущен: {url[:50]}...")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения лида {url[:50]}...: {e}")
            return False
    
    async def close(self):
        """Закрывает соединение с базой данных"""
        if self.conn:
            await self.conn.close()
            self.conn = None
            logger.debug("Соединение с базой данных закрыто")
