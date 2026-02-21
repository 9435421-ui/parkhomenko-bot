"""
Database Schema Synchronization Script for Production
=====================================================

This script synchronizes the production database schema with the code expectations
after the "Deep Cleaning" refactor.

Run this on the production server:
    python migrations/sync_production_schema.py

It will:
1. Create missing tables (spy_leads, users, user_states, etc.)
2. Add missing columns to existing tables
3. Initialize default data
4. Verify schema integrity

Safe to run multiple times - checks before altering.
"""
import sqlite3
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default database path (adjust if needed)
DEFAULT_DB_PATH = "database/bot.db"


def get_table_columns(cursor, table_name):
    """Get list of column names for a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def table_exists(cursor, table_name):
    """Check if table exists"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None


def column_exists(cursor, table_name, column_name):
    """Check if column exists in table"""
    columns = get_table_columns(cursor, table_name)
    return column_name in columns


def migrate_database(db_path: str = None):
    """Main migration function"""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    
    # Resolve absolute path
    db_path = Path(db_path).resolve()
    
    if not db_path.exists():
        logger.error(f"❌ Database file not found: {db_path}")
        logger.info("Creating database directory...")
        db_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"📂 Connecting to database: {db_path}")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # ============================================
        # 1. CREATE spy_leads TABLE (CRITICAL)
        # ============================================
        if not table_exists(cursor, 'spy_leads'):
            logger.info("🔨 Creating spy_leads table...")
            cursor.execute("""
                CREATE TABLE spy_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    author_id TEXT,
                    username TEXT,
                    profile_url TEXT,
                    text TEXT,
                    url TEXT NOT NULL,
                    pain_stage TEXT,
                    priority_score INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    contacted_at TIMESTAMP NULL,
                    sent_to_hot_leads INTEGER DEFAULT 0
                )
            """)
            logger.info("✅ Created spy_leads table")
        else:
            logger.info("✅ spy_leads table exists")
            
            # Add missing columns
            columns = get_table_columns(cursor, 'spy_leads')
            
            if 'pain_stage' not in columns:
                cursor.execute("ALTER TABLE spy_leads ADD COLUMN pain_stage TEXT")
                logger.info("✅ Added pain_stage column to spy_leads")
            
            if 'priority_score' not in columns:
                cursor.execute("ALTER TABLE spy_leads ADD COLUMN priority_score INTEGER")
                logger.info("✅ Added priority_score column to spy_leads")
            
            if 'contacted_at' not in columns:
                cursor.execute("ALTER TABLE spy_leads ADD COLUMN contacted_at TIMESTAMP NULL")
                logger.info("✅ Added contacted_at column to spy_leads")
            
            if 'sent_to_hot_leads' not in columns:
                cursor.execute("ALTER TABLE spy_leads ADD COLUMN sent_to_hot_leads INTEGER DEFAULT 0")
                logger.info("✅ Added sent_to_hot_leads column to spy_leads")
        
        # ============================================
        # 2. CREATE users TABLE
        # ============================================
        if not table_exists(cursor, 'users'):
            logger.info("🔨 Creating users table...")
            cursor.execute("""
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("✅ Created users table")
        else:
            logger.info("✅ users table exists")
        
        # ============================================
        # 3. CREATE user_states TABLE
        # ============================================
        if not table_exists(cursor, 'user_states'):
            logger.info("🔨 Creating user_states table...")
            cursor.execute("""
                CREATE TABLE user_states (
                    user_id INTEGER PRIMARY KEY,
                    mode TEXT,
                    quiz_step INTEGER DEFAULT 0,
                    name TEXT,
                    phone TEXT,
                    extra_contact TEXT,
                    object_type TEXT,
                    city TEXT,
                    floor TEXT,
                    total_floors TEXT,
                    remodeling_status TEXT,
                    change_plan TEXT,
                    bti_status TEXT,
                    consent_given BOOLEAN DEFAULT 0,
                    contact_received BOOLEAN DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            logger.info("✅ Created user_states table")
        else:
            logger.info("✅ user_states table exists")
        
        # ============================================
        # 4. CREATE dialog_history TABLE
        # ============================================
        if not table_exists(cursor, 'dialog_history'):
            logger.info("🔨 Creating dialog_history table...")
            cursor.execute("""
                CREATE TABLE dialog_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    role TEXT,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            logger.info("✅ Created dialog_history table")
        else:
            logger.info("✅ dialog_history table exists")
        
        # ============================================
        # 5. UPDATE leads TABLE (add missing columns)
        # ============================================
        if table_exists(cursor, 'leads'):
            logger.info("🔍 Checking leads table columns...")
            columns = get_table_columns(cursor, 'leads')
            
            if 'area' not in columns:
                cursor.execute("ALTER TABLE leads ADD COLUMN area TEXT")
                logger.info("✅ Added area column to leads")
            
            if 'extra_questions' not in columns:
                cursor.execute("ALTER TABLE leads ADD COLUMN extra_questions TEXT")
                logger.info("✅ Added extra_questions column to leads")
            
            if 'thread_id' not in columns:
                cursor.execute("ALTER TABLE leads ADD COLUMN thread_id INTEGER")
                logger.info("✅ Added thread_id column to leads")
        else:
            logger.warning("⚠️ leads table not found - skipping column updates")
        
        # ============================================
        # 6. UPDATE content_plan TABLE (add missing columns)
        # ============================================
        if table_exists(cursor, 'content_plan'):
            logger.info("🔍 Checking content_plan table columns...")
            columns = get_table_columns(cursor, 'content_plan')
            
            if 'channel' not in columns:
                cursor.execute("ALTER TABLE content_plan ADD COLUMN channel TEXT DEFAULT 'terion'")
                logger.info("✅ Added channel column to content_plan")
            
            if 'theme' not in columns:
                cursor.execute("ALTER TABLE content_plan ADD COLUMN theme TEXT")
                logger.info("✅ Added theme column to content_plan")
            
            if 'image_url' not in columns:
                cursor.execute("ALTER TABLE content_plan ADD COLUMN image_url TEXT")
                logger.info("✅ Added image_url column to content_plan")
            
            if 'admin_id' not in columns:
                cursor.execute("ALTER TABLE content_plan ADD COLUMN admin_id INTEGER DEFAULT NULL")
                logger.info("✅ Added admin_id column to content_plan")
            
            if 'published_at' not in columns:
                cursor.execute("ALTER TABLE content_plan ADD COLUMN published_at TIMESTAMP DEFAULT NULL")
                logger.info("✅ Added published_at column to content_plan")
        else:
            logger.warning("⚠️ content_plan table not found - skipping column updates")
        
        # ============================================
        # 7. CREATE target_resources TABLE
        # ============================================
        if not table_exists(cursor, 'target_resources'):
            logger.info("🔨 Creating target_resources table...")
            cursor.execute("""
                CREATE TABLE target_resources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL CHECK(type IN ('telegram', 'vk')),
                    link TEXT NOT NULL UNIQUE,
                    title TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    last_post_id INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT NULL,
                    status TEXT DEFAULT 'pending',
                    platform TEXT NULL,
                    geo_tag TEXT NULL,
                    participants_count INTEGER NULL,
                    is_high_priority INTEGER DEFAULT 0,
                    priority INTEGER DEFAULT 5,
                    last_scanned_at TIMESTAMP NULL,
                    last_lead_at TIMESTAMP NULL
                )
            """)
            logger.info("✅ Created target_resources table")
        else:
            logger.info("✅ target_resources table exists")
            # Add missing columns
            columns = get_table_columns(cursor, 'target_resources')
            
            for col, ctype, default in [
                ('notes', 'TEXT', 'NULL'),
                ('status', 'TEXT', "DEFAULT 'pending'"),
                ('platform', 'TEXT', 'NULL'),
                ('geo_tag', 'TEXT', 'NULL'),
                ('participants_count', 'INTEGER', 'NULL'),
                ('is_high_priority', 'INTEGER', 'DEFAULT 0'),
                ('priority', 'INTEGER', 'DEFAULT 5'),
                ('last_scanned_at', 'TIMESTAMP', 'NULL'),
                ('last_lead_at', 'TIMESTAMP', 'NULL'),
            ]:
                if col not in columns:
                    try:
                        cursor.execute(f"ALTER TABLE target_resources ADD COLUMN {col} {ctype} {default}")
                        logger.info(f"✅ Added {col} column to target_resources")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to add {col}: {e}")
        
        # ============================================
        # 8. CREATE spy_keywords TABLE
        # ============================================
        if not table_exists(cursor, 'spy_keywords'):
            logger.info("🔨 Creating spy_keywords table...")
            cursor.execute("""
                CREATE TABLE spy_keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL UNIQUE,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("✅ Created spy_keywords table")
        else:
            logger.info("✅ spy_keywords table exists")
        
        # ============================================
        # 9. CREATE bot_settings TABLE
        # ============================================
        if not table_exists(cursor, 'bot_settings'):
            logger.info("🔨 Creating bot_settings table...")
            cursor.execute("""
                CREATE TABLE bot_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("✅ Created bot_settings table")
        else:
            logger.info("✅ bot_settings table exists")
        
        # ============================================
        # 10. CREATE clients_birthdays TABLE
        # ============================================
        if not table_exists(cursor, 'clients_birthdays'):
            logger.info("🔨 Creating clients_birthdays table...")
            cursor.execute("""
                CREATE TABLE clients_birthdays (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT,
                    birth_date DATE NOT NULL,
                    channel TEXT DEFAULT 'telegram',
                    greeting_sent BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            logger.info("✅ Created clients_birthdays table")
        else:
            logger.info("✅ clients_birthdays table exists")
        
        # ============================================
        # 11. CREATE content_history TABLE
        # ============================================
        if not table_exists(cursor, 'content_history'):
            logger.info("🔨 Creating content_history table...")
            cursor.execute("""
                CREATE TABLE content_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_text TEXT,
                    image_url TEXT,
                    model_used VARCHAR(50),
                    cost_rub DECIMAL(10, 2),
                    platform VARCHAR(20),
                    channel VARCHAR(50),
                    post_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_archived BOOLEAN DEFAULT FALSE
                )
            """)
            logger.info("✅ Created content_history table")
        else:
            logger.info("✅ content_history table exists")
        
        # ============================================
        # 12. CREATE sales_templates TABLE
        # ============================================
        if not table_exists(cursor, 'sales_templates'):
            logger.info("🔨 Creating sales_templates table...")
            cursor.execute("""
                CREATE TABLE sales_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL UNIQUE,
                    body TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("✅ Created sales_templates table")
        else:
            logger.info("✅ sales_templates table exists")
        
        # ============================================
        # 13. CREATE sales_conversations TABLE
        # ============================================
        if not table_exists(cursor, 'sales_conversations'):
            logger.info("🔨 Creating sales_conversations table...")
            cursor.execute("""
                CREATE TABLE sales_conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    post_id TEXT NOT NULL,
                    keyword TEXT,
                    context TEXT,
                    object_type TEXT,
                    sales_step INTEGER DEFAULT 1,
                    document_received BOOLEAN DEFAULT FALSE,
                    skipped_steps TEXT,
                    reminder_attempts INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    sales_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_interaction_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_reminder_at TIMESTAMP NULL,
                    completed BOOLEAN DEFAULT FALSE,
                    UNIQUE(user_id, source_type, source_id, post_id)
                )
            """)
            logger.info("✅ Created sales_conversations table")
        else:
            logger.info("✅ sales_conversations table exists")
        
        # ============================================
        # 14. INITIALIZE DEFAULT DATA
        # ============================================
        logger.info("🔧 Initializing default data...")
        
        # bot_settings
        cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('spy_notify_enabled', '1')")
        
        # sales_templates
        cursor.execute("INSERT OR IGNORE INTO sales_templates (key, body) VALUES (?, ?)",
                      ('mji_prescription', 'Срочный выезд и аудит документов'))
        cursor.execute("INSERT OR IGNORE INTO sales_templates (key, body) VALUES (?, ?)",
                      ('keys_design', 'Проверка проекта на реализуемость'))
        
        # Migrate target_resources status
        if table_exists(cursor, 'target_resources'):
            cursor.execute("UPDATE target_resources SET status = 'active' WHERE is_active = 1 AND (status IS NULL OR status = '')")
            cursor.execute("UPDATE target_resources SET status = 'archived' WHERE (is_active = 0 OR is_active IS NULL) AND (status IS NULL OR status = '')")
            cursor.execute("UPDATE target_resources SET platform = type WHERE platform IS NULL OR platform = ''")
        
        conn.commit()
        logger.info("✅ Default data initialized")
        
        # ============================================
        # 15. VERIFICATION
        # ============================================
        logger.info("\n" + "="*60)
        logger.info("📊 VERIFICATION REPORT")
        logger.info("="*60)
        
        required_tables = [
            'spy_leads', 'users', 'user_states', 'dialog_history',
            'target_resources', 'spy_keywords', 'bot_settings',
            'clients_birthdays', 'content_history', 'sales_templates',
            'sales_conversations'
        ]
        
        for table in required_tables:
            if table_exists(cursor, table):
                logger.info(f"✅ {table} exists")
            else:
                logger.error(f"❌ {table} MISSING")
        
        # Check spy_leads columns
        if table_exists(cursor, 'spy_leads'):
            columns = get_table_columns(cursor, 'spy_leads')
            required_columns = ['pain_stage', 'priority_score', 'contacted_at', 'sent_to_hot_leads']
            logger.info("\n📋 spy_leads columns:")
            for col in required_columns:
                if col in columns:
                    logger.info(f"  ✅ {col}")
                else:
                    logger.error(f"  ❌ {col} MISSING")
        
        logger.info("\n" + "="*60)
        logger.info("✅ Migration completed successfully!")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync production database schema')
    parser.add_argument('--db-path', type=str, default=DEFAULT_DB_PATH,
                       help=f'Path to database file (default: {DEFAULT_DB_PATH})')
    
    args = parser.parse_args()
    
    try:
        migrate_database(args.db_path)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
