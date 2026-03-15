import aiosqlite
import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class HunterDatabase:
    def __init__(self, db_path: str = "database/bot.db"):
        self.db_path = db_path

    async def init_db(self):
        """Инициализация таблиц для Lead Hunter"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS hunter_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_id TEXT UNIQUE,
                    source TEXT,
                    content TEXT,
                    author_id TEXT,
                    author_name TEXT,
                    url TEXT,
                    status TEXT DEFAULT 'new',
                    score REAL DEFAULT 0,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS hunter_targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_id TEXT UNIQUE,
                    target_type TEXT,
                    name TEXT,
                    last_scanned TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    metadata TEXT
                )
            """)
            await db.commit()

    async def save_lead(self, lead_data: Dict[str, Any]) -> bool:
        """Сохранение найденного лида"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR IGNORE INTO hunter_leads 
                    (external_id, source, content, author_id, author_name, url, score, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    lead_data.get('external_id'),
                    lead_data.get('source'),
                    lead_data.get('content'),
                    lead_data.get('author_id'),
                    lead_data.get('author_name'),
                    lead_data.get('url'),
                    lead_data.get('score', 0),
                    json.dumps(lead_data.get('metadata', {}))
                ))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error saving lead: {e}")
            return False

    async def get_new_leads(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Получение новых необработанных лидов"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM hunter_leads WHERE status = 'new' ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def update_lead_status(self, lead_id: int, status: str):
        """Обновление статуса лида"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE hunter_leads SET status = ?, processed_at = ? WHERE id = ?",
                (status, datetime.now().isoformat(), lead_id)
            )
            await db.commit()

    async def add_target(self, target_data: Dict[str, Any]):
        """Добавление цели для мониторинга"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO hunter_targets 
                (target_id, target_type, name, metadata)
                VALUES (?, ?, ?, ?)
            """, (
                target_data.get('target_id'),
                target_data.get('target_type'),
                target_data.get('name'),
                json.dumps(target_data.get('metadata', {}))
            ))
            await db.commit()

    async def get_active_targets(self) -> List[Dict[str, Any]]:
        """Получение списка активных целей"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM hunter_targets WHERE is_active = 1") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
