# -*- coding: utf-8 -*-
"""Скрипт для активации постов в контент-плане"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import db
from datetime import datetime


async def main():
    try:
        await db.connect()
        
        async with db.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT id, title, created_at FROM content_plan WHERE status = 'draft' ORDER BY created_at DESC LIMIT 2"
            )
            posts = await cursor.fetchall()
        
        if not posts:
            print("No draft posts found")
            return
        
        print(f"Found {len(posts)} posts to activate:")
        
        for post in posts:
            post_id = post[0]
            title = post[1] or f"Post #{post_id}"
            
            try:
                await db.update_content_plan_entry(
                    post_id=post_id,
                    status='approved',
                    publish_date=datetime.now()
                )
                print(f"Activated post #{post_id}: {title[:50]}")
            except Exception as e:
                print(f"Error activating post #{post_id}: {e}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if db.conn:
            await db.close()


if __name__ == "__main__":
    asyncio.run(main())
