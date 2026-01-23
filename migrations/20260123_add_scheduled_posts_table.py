"""
Migration: Add scheduled_posts table for autoposter
Date: 2026-01-23
Author: VS Code AI
"""

import sqlite3
import os

def migrate():
    """Apply the migration"""
    db_path = os.getenv("DB_PATH", "db/parkhomenko_bot.db")
    if db_path.startswith("sqlite:///"):
        db_path = db_path.replace("sqlite:///", "")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create scheduled_posts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_posts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id   TEXT NOT NULL,
            text         TEXT NOT NULL,
            image_path   TEXT,
            scheduled_at TEXT NOT NULL,
            status       TEXT NOT NULL,
            created_at   TEXT NOT NULL,
            sent_at      TEXT
        )
    """)

    # Create index for scheduled_at and status for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_scheduled_posts_scheduled_at_status
        ON scheduled_posts(scheduled_at, status)
    """)

    conn.commit()
    conn.close()

    print("✅ Migration 20260123_add_scheduled_posts_table applied successfully")
    print("📅 Added scheduled_posts table for autoposter")

if __name__ == "__main__":
    migrate()
