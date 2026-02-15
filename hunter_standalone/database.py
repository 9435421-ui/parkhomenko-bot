import aiosqlite
import os
import json
from datetime import datetime
from typing import Optional, List, Dict

class HunterDatabase:
    """База данных для модуля Lead Hunter (Шпион)"""

    def __init__(self, db_path: str = "potential_leads.db"):
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Подключение к базе данных"""
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self._create_tables()

    async def _create_tables(self):
        """Создание таблиц"""
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self.conn.commit()

    async def save_lead(self, lead_data: Dict) -> bool:
        """Сохранение лида с защитой от дублей (Анти-спам)"""
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO potential_leads
                    (message_url, content, intent, hotness, geo, context_summary)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    lead_data['url'],
                    lead_data['content'],
                    lead_data['intent'],
                    lead_data['hotness'],
                    lead_data['geo'],
                    lead_data['context_summary']
                ))
                await self.conn.commit()
                return True
        except aiosqlite.IntegrityError:
            # Лид уже существует (по message_url)
            return False

    async def get_all_leads(self) -> List[Dict]:
        """Получение всех найденных лидов"""
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM potential_leads ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def export_to_json(self, file_path: str = "leads_export.json"):
        """Экспорт в JSON (Data Pipeline)"""
        leads = await self.get_all_leads()
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(leads, f, ensure_ascii=False, indent=4)
