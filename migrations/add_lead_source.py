#!/usr/bin/env python3
"""
Migration: Add source field to leads table
"""

import os
import sys
import asyncio

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db

async def migrate():
    """Add source field to leads table"""
    try:
        await db.connect()

        # Check if source column already exists
        cursor = await db.conn.execute("PRAGMA table_info(leads)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        if 'source' not in column_names:
            print("Adding 'source' column to leads table...")
            await db.conn.execute("ALTER TABLE leads ADD COLUMN source TEXT")
            await db.conn.commit()
            print("✅ Migration completed: Added 'source' column to leads table")
        else:
            print("ℹ️ Migration skipped: 'source' column already exists")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False
    finally:
        await db.disconnect()

    return True

if __name__ == "__main__":
    success = asyncio.run(migrate())
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")
        sys.exit(1)
