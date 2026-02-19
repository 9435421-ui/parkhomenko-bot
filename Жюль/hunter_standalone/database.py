import aiosqlite
import os
import json
from datetime import datetime
from typing import Optional, List, Dict

class HunterDatabase:
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Пытаемся взять путь из окружения или используем стандартный путь в папке database
            db_path = os.getenv("POTENTIAL_LEADS_DB")
            if not db_path:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                db_path = os.path.join(base_dir, "database", "potential_leads.db")
        
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self._create_tables()

    async def _create_tables(self):
        async with self.conn.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS potential_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_url TEXT UNIQUE,
                    content TEXT,
                    intent TEXT,
                    hotness INTEGER,
                    geo TEXT,
                    context_summary TEXT,
                    pain_stage TEXT,
                    priority_score INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Migration
            for col, ctype in [("pain_stage", "TEXT"), ("priority_score", "INTEGER")]:
                try:
                    await cursor.execute(f"ALTER TABLE potential_leads ADD COLUMN {col} {ctype}")
                except Exception:
                    pass
            await self.conn.commit()

    async def save_lead(self, lead_data: Dict) -> bool:
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO potential_leads 
                    (message_url, content, intent, hotness, geo, context_summary, pain_stage, priority_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    lead_data['url'], lead_data['content'], lead_data['intent'],
                    lead_data['hotness'], lead_data['geo'], lead_data['context_summary'],
                    lead_data.get('pain_stage'), lead_data.get('priority_score')
                ))
                await self.conn.commit()
                return True
        except aiosqlite.IntegrityError:
            return False

    async def get_latest_hot_leads(self, limit: int = 3) -> List[Dict]:
        """Последние горячие темы: по hotness и дате, для выбора темы новости."""
        if not self.conn:
            await self.connect()
        async with self.conn.cursor() as cursor:
            await cursor.execute("""
                SELECT content, intent, hotness, created_at
                FROM potential_leads
                WHERE content IS NOT NULL AND TRIM(content) != ''
                ORDER BY hotness DESC, created_at DESC
                LIMIT ?
            """, (limit,))
            rows = await cursor.fetchall()
        return [
            {"content": row[0], "intent": row[1], "hotness": row[2], "created_at": row[3]}
            for row in rows
        ]
