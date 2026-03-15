import os
import sqlite3
import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class HunterDatabase:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.getenv("DB_PATH", "parkhomenko_bot.db")
        self.db_path = db_path
        self.conn = None

    async def connect(self):
        """Установка соединения с БД (синхронный sqlite3 в асинхронной обертке для простоты)"""
        if not self.conn:
            try:
                self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
                self._init_tables()
            except Exception as e:
                logger.error(f"HunterDatabase.connect error: {e}")

    def _init_tables(self):
        """Инициализация таблиц если их нет"""
        cursor = self.conn.cursor()
        # Таблица лидов (если еще нет в основной базе)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hunter_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                url TEXT UNIQUE,
                intent TEXT,
                hotness INTEGER,
                geo TEXT,
                context_summary TEXT,
                recommendation TEXT,
                pain_level INTEGER,
                pain_stage TEXT,
                priority_score REAL,
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP
            )
        """)
        self.conn.commit()

    async def save_lead(self, lead_data: Dict[str, Any]) -> bool:
        """Сохранение найденного лида"""
        if not self.conn:
            await self.connect()
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO hunter_leads 
                (content, url, intent, hotness, geo, context_summary, 
                 recommendation, pain_level, pain_stage, priority_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lead_data.get('content'),
                lead_data.get('url'),
                lead_data.get('intent'),
                lead_data.get('hotness'),
                lead_data.get('geo'),
                lead_data.get('context_summary'),
                lead_data.get('recommendation'),
                lead_data.get('pain_level'),
                lead_data.get('pain_stage'),
                lead_data.get('priority_score')
            ))
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"HunterDatabase.save_lead error: {e}")
            return False

    async def get_latest_hot_leads(self, limit: int = 10, days: int = 7) -> List[Dict[str, Any]]:
        """Получение горячих лидов за последние N дней"""
        if not self.conn:
            await self.connect()
            
        try:
            cursor = self.conn.cursor()
            since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                SELECT * FROM hunter_leads 
                WHERE hotness >= 3 AND created_at >= ? 
                ORDER BY created_at DESC LIMIT ?
            """, (since, limit))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"HunterDatabase.get_latest_hot_leads error: {e}")
            return []

    async def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
