#!/usr/bin/env python3
import asyncio
from database import db

async def cleanup():
    await db.connect()

    # Delete balcony-related drafts
    await db.conn.execute("""
    DELETE FROM content_plan
    WHERE status = 'draft'
      AND (body LIKE '%балкон%' OR body LIKE '%утепл%' OR body LIKE '%промерзающ%')
    """)

    await db.conn.commit()
    print("Cleaned up balcony drafts")

asyncio.run(cleanup())
