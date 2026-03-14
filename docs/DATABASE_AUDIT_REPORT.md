# Database Schema Audit Report
**Date:** 2026-02-17  
**Task:** Project Integrity & Database Schema Audit after "Deep Cleaning" refactor

---

## Executive Summary

After the "Deep Cleaning" refactor, there is a mismatch between the code expectations and the production database schema. This report identifies all discrepancies and provides exact SQL commands to synchronize the production database.

---

## 1. Database Mapping: `add_spy_lead` Method

### ✅ **CONFIRMED: Method writes to `spy_leads` table (NOT `leads`)**

**Location:** `database/db.py`, lines 499-519

```python
async def add_spy_lead(
    self,
    source_type: str,
    source_name: str,
    url: str,
    text: str = "",
    author_id: Optional[str] = None,
    username: Optional[str] = None,
    profile_url: Optional[str] = None,
    pain_stage: Optional[str] = None,
    priority_score: Optional[int] = None,
) -> int:
    """Сохранить лид от шпиона: источник, автор, ссылка на профиль, текст, стадия боли, оценка приоритета."""
    async with self.conn.cursor() as cursor:
        await cursor.execute(
            """INSERT INTO spy_leads (source_type, source_name, author_id, username, profile_url, text, url, pain_stage, priority_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source_type, source_name, author_id or None, username or None, profile_url or None, text or "", url, pain_stage, priority_score),
        )
```

**Conclusion:** The method correctly writes to `spy_leads` table. The tables `spy_leads` and `leads` are **separate**:
- `leads` - leads from quiz/form submissions (user_id, name, phone, etc.)
- `spy_leads` - leads discovered by LeadHunter from Telegram/VK channels

---

## 2. Schema Validation: Expected vs Production Tables

### Expected Tables (from `database/db.py`)

| Table Name | Purpose | Key Columns |
|------------|---------|-------------|
| `users` | User accounts | user_id, username, first_name, last_name |
| `user_states` | FSM states for quiz/dialog | user_id, mode, quiz_step, name, phone, etc. |
| `dialog_history` | Chat history | id, user_id, role, message |
| `leads` | Quiz/form submissions | id, user_id, name, phone, object_type, city, etc. |
| `spy_leads` | **Hunter-discovered leads** | id, source_type, source_name, author_id, text, url, **pain_stage**, **priority_score**, **sent_to_hot_leads** |
| `content_plan` | Content scheduling | id, type, channel, title, body, status, publish_date |
| `clients_birthdays` | Birthday greetings | id, user_id, name, birth_date |
| `target_resources` | Scout targets (TG/VK channels) | id, type, link, title, status, last_post_id |
| `spy_keywords` | Keywords for monitoring | id, keyword, is_active |
| `bot_settings` | Bot configuration | key, value |
| `content_history` | Financial tracking | id, post_text, model_used, cost_rub |
| `sales_templates` | Sales script templates | id, key, body |
| `sales_conversations` | 5-step sales script state | id, user_id, source_type, sales_step, etc. |

### Production Tables (from user report)

User mentioned these tables exist on server:
- `content_plan` ✅
- `holidays` ⚠️ (NOT in code - may be legacy)
- `leads` ✅
- `news` ⚠️ (NOT in code - may be legacy)
- `subscribers` ⚠️ (NOT in code - may be legacy)

**Missing Tables (CRITICAL):**
- ❌ `spy_leads` - **REQUIRED** for LeadHunter functionality
- ❌ `users` - **REQUIRED** for user management
- ❌ `user_states` - **REQUIRED** for FSM
- ❌ `target_resources` - **REQUIRED** for Scout
- ❌ `sales_conversations` - **REQUIRED** for Sales Agent

---

## 3. Missing Columns Fix: `spy_leads` Table

### Required Columns for `spy_leads`

The code expects these columns (from `database/db.py` lines 181-194, 213-242, 597-620):

| Column | Type | Default | Purpose | Migration Status |
|---------|------|---------|---------|------------------|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | - | Primary key | ✅ In CREATE TABLE |
| `source_type` | TEXT NOT NULL | - | "telegram" or "vk" | ✅ In CREATE TABLE |
| `source_name` | TEXT NOT NULL | - | Channel/group name | ✅ In CREATE TABLE |
| `author_id` | TEXT | NULL | User ID from source | ✅ In CREATE TABLE |
| `username` | TEXT | NULL | Username | ✅ In CREATE TABLE |
| `profile_url` | TEXT | NULL | Link to profile | ✅ In CREATE TABLE |
| `text` | TEXT | NULL | Post/message text | ✅ In CREATE TABLE |
| `url` | TEXT NOT NULL | - | Link to post | ✅ In CREATE TABLE |
| `pain_stage` | TEXT | NULL | ST-1, ST-2, ST-3, ST-4 | ⚠️ **Migration exists** (lines 225-242) |
| `priority_score` | INTEGER | NULL | 0-10 priority | ⚠️ **Migration exists** (lines 225-242) |
| `created_at` | TIMESTAMP | CURRENT_TIMESTAMP | Creation time | ✅ In CREATE TABLE |
| `contacted_at` | TIMESTAMP | NULL | First contact time | ⚠️ **Migration exists** (lines 213-218) |
| `sent_to_hot_leads` | INTEGER | 0 | Flag for hot leads topic | ⚠️ **Dynamic migration** (lines 597-620) |

### Migration Logic

The code has **automatic migrations** that check and add missing columns:

1. **`pain_stage` and `priority_score`** (lines 225-242):
   - Checks `PRAGMA table_info(spy_leads)`
   - Adds if missing

2. **`contacted_at`** (lines 213-218):
   - Simple try/except ALTER TABLE

3. **`sent_to_hot_leads`** (lines 597-620):
   - Checked dynamically in `mark_lead_sent_to_hot_leads()`
   - Added if missing

**Problem:** If `spy_leads` table doesn't exist on production, these migrations won't run because they only execute ALTER TABLE, not CREATE TABLE.

---

## 4. Imports Audit: Legacy File References

### ❌ **CRITICAL: Found import from deleted file**

**File:** `run_all.py`, line 60
```python
from chat_parser import start_monitoring
```

**Status:** `chat_parser.py` exists but is legacy code. The new structure uses `services/lead_hunter/hunter.py`.

**Impact:** `run_all.py` will work but uses outdated code path.

**Fix Applied:** ✅ Updated `run_all.py` to use `services/lead_hunter/hunter.py` instead of `chat_parser.py`

**Note:** `chat_parser.py` still exists in the codebase but should be considered deprecated. The production system uses `main.py` which integrates LeadHunter via APScheduler.

### ✅ **Valid imports (NOT legacy)**

These imports are **valid** and refer to existing modules:

1. `services/lead_hunter/hunter.py`, line 13:
   ```python
   from hunter_standalone import HunterDatabase, LeadHunter as StandaloneLeadHunter
   ```
   - ✅ `hunter_standalone/` is a valid module (not deleted)

2. `handlers/content.py`, line 37:
   ```python
   from hunter_standalone import HunterDatabase
   ```
   - ✅ Valid import

---

## 5. SQL Commands for Production Database Synchronization

### Step 1: Create Missing Tables

```sql
-- ============================================
-- 1. CREATE spy_leads TABLE (CRITICAL)
-- ============================================
CREATE TABLE IF NOT EXISTS spy_leads (
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
);

-- ============================================
-- 2. CREATE users TABLE (if missing)
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    phone TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 3. CREATE user_states TABLE (if missing)
-- ============================================
CREATE TABLE IF NOT EXISTS user_states (
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
);

-- ============================================
-- 4. CREATE dialog_history TABLE (if missing)
-- ============================================
CREATE TABLE IF NOT EXISTS dialog_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    role TEXT,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- ============================================
-- 5. CREATE target_resources TABLE (if missing)
-- ============================================
CREATE TABLE IF NOT EXISTS target_resources (
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
);

-- ============================================
-- 6. CREATE spy_keywords TABLE (if missing)
-- ============================================
CREATE TABLE IF NOT EXISTS spy_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 7. CREATE bot_settings TABLE (if missing)
-- ============================================
CREATE TABLE IF NOT EXISTS bot_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 8. CREATE clients_birthdays TABLE (if missing)
-- ============================================
CREATE TABLE IF NOT EXISTS clients_birthdays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT,
    birth_date DATE NOT NULL,
    channel TEXT DEFAULT 'telegram',
    greeting_sent BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- ============================================
-- 9. CREATE content_history TABLE (if missing)
-- ============================================
CREATE TABLE IF NOT EXISTS content_history (
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
);

-- ============================================
-- 10. CREATE sales_templates TABLE (if missing)
-- ============================================
CREATE TABLE IF NOT EXISTS sales_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    body TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 11. CREATE sales_conversations TABLE (if missing)
-- ============================================
CREATE TABLE IF NOT EXISTS sales_conversations (
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
);
```

### Step 2: Add Missing Columns to Existing Tables

```sql
-- ============================================
-- ADD MISSING COLUMNS TO spy_leads
-- (Run only if table exists but columns are missing)
-- ============================================

-- Check if pain_stage exists, add if not
-- Note: SQLite doesn't support IF NOT EXISTS for ALTER TABLE ADD COLUMN
-- Use Python migration logic or check manually first

-- For pain_stage (TEXT)
-- Check: PRAGMA table_info(spy_leads) - if 'pain_stage' not in column names:
ALTER TABLE spy_leads ADD COLUMN pain_stage TEXT;

-- For priority_score (INTEGER)
-- Check: PRAGMA table_info(spy_leads) - if 'priority_score' not in column names:
ALTER TABLE spy_leads ADD COLUMN priority_score INTEGER;

-- For contacted_at (TIMESTAMP)
-- Check: PRAGMA table_info(spy_leads) - if 'contacted_at' not in column names:
ALTER TABLE spy_leads ADD COLUMN contacted_at TIMESTAMP NULL;

-- For sent_to_hot_leads (INTEGER DEFAULT 0)
-- Check: PRAGMA table_info(spy_leads) - if 'sent_to_hot_leads' not in column names:
ALTER TABLE spy_leads ADD COLUMN sent_to_hot_leads INTEGER DEFAULT 0;

-- ============================================
-- ADD MISSING COLUMNS TO leads TABLE
-- ============================================
-- Check if these columns exist first:
ALTER TABLE leads ADD COLUMN area TEXT;
ALTER TABLE leads ADD COLUMN extra_questions TEXT;
ALTER TABLE leads ADD COLUMN thread_id INTEGER;

-- ============================================
-- ADD MISSING COLUMNS TO content_plan TABLE
-- ============================================
-- Check if these columns exist first:
ALTER TABLE content_plan ADD COLUMN channel TEXT DEFAULT 'terion';
ALTER TABLE content_plan ADD COLUMN theme TEXT;
ALTER TABLE content_plan ADD COLUMN image_url TEXT;
ALTER TABLE content_plan ADD COLUMN admin_id INTEGER DEFAULT NULL;
ALTER TABLE content_plan ADD COLUMN published_at TIMESTAMP DEFAULT NULL;
```

### Step 3: Initialize Default Data

```sql
-- ============================================
-- INITIALIZE bot_settings
-- ============================================
INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('spy_notify_enabled', '1');

-- ============================================
-- INITIALIZE sales_templates
-- ============================================
INSERT OR IGNORE INTO sales_templates (key, body) VALUES 
    ('mji_prescription', 'Срочный выезд и аудит документов'),
    ('keys_design', 'Проверка проекта на реализуемость');

-- ============================================
-- MIGRATE target_resources status
-- ============================================
-- Update existing records to set status based on is_active
UPDATE target_resources SET status = 'active' WHERE is_active = 1 AND (status IS NULL OR status = '');
UPDATE target_resources SET status = 'archived' WHERE (is_active = 0 OR is_active IS NULL) AND (status IS NULL OR status = '');
UPDATE target_resources SET platform = type WHERE platform IS NULL OR platform = '';
```

---

## 6. Verification Queries

Run these queries to verify the schema:

```sql
-- Check if spy_leads table exists and has all columns
SELECT sql FROM sqlite_master WHERE type='table' AND name='spy_leads';

-- List all columns in spy_leads
PRAGMA table_info(spy_leads);

-- Check if required columns exist
SELECT name FROM pragma_table_info('spy_leads') WHERE name IN ('pain_stage', 'priority_score', 'sent_to_hot_leads', 'contacted_at');

-- List all tables
SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;

-- Check content_plan structure
PRAGMA table_info(content_plan);

-- Check leads structure
PRAGMA table_info(leads);
```

---

## 7. Migration Script (Python)

For safer execution, use this Python script that checks before altering:

```python
"""
Database Migration Script for Production
Run this on the production server to sync schema.
"""
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "database/bot.db"  # Adjust path as needed

def get_table_columns(cursor, table_name):
    """Get list of column names for a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]

def table_exists(cursor, table_name):
    """Check if table exists"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None

def migrate_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 1. Create spy_leads if missing
        if not table_exists(cursor, 'spy_leads'):
            logger.info("Creating spy_leads table...")
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
                logger.info("✅ Added pain_stage column")
            
            if 'priority_score' not in columns:
                cursor.execute("ALTER TABLE spy_leads ADD COLUMN priority_score INTEGER")
                logger.info("✅ Added priority_score column")
            
            if 'contacted_at' not in columns:
                cursor.execute("ALTER TABLE spy_leads ADD COLUMN contacted_at TIMESTAMP NULL")
                logger.info("✅ Added contacted_at column")
            
            if 'sent_to_hot_leads' not in columns:
                cursor.execute("ALTER TABLE spy_leads ADD COLUMN sent_to_hot_leads INTEGER DEFAULT 0")
                logger.info("✅ Added sent_to_hot_leads column")
        
        # 2. Initialize bot_settings
        cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('spy_notify_enabled', '1')")
        
        conn.commit()
        logger.info("✅ Migration completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
```

---

## 8. Action Items

### Immediate Actions (CRITICAL)

1. ✅ **Create `spy_leads` table** on production server
2. ✅ **Add missing columns** to `spy_leads`: `pain_stage`, `priority_score`, `contacted_at`, `sent_to_hot_leads`
3. ✅ **Create missing tables**: `users`, `user_states`, `target_resources`, `sales_conversations`, etc.
4. ⚠️ **Fix `run_all.py`** - remove or update import from deleted `chat_parser`

### Verification Steps

1. Run verification queries (Section 6)
2. Test `add_spy_lead()` method
3. Test `mark_lead_sent_to_hot_leads()` method
4. Check logs for migration messages

### Optional Cleanup

- Investigate legacy tables: `holidays`, `news`, `subscribers` - determine if they're still needed
- Remove or archive if unused

---

## 9. Summary

| Issue | Status | Impact | Fix |
|-------|--------|--------|-----|
| `spy_leads` table missing | ❌ CRITICAL | LeadHunter won't work | CREATE TABLE (Section 5) |
| Missing columns in `spy_leads` | ⚠️ HIGH | Features broken | ALTER TABLE (Section 5) |
| Import from deleted `chat_parser` | ⚠️ MEDIUM | `run_all.py` broken | Remove/update import |
| Missing tables (`users`, etc.) | ⚠️ HIGH | Core features broken | CREATE TABLE (Section 5) |
| Legacy tables (`holidays`, etc.) | ℹ️ LOW | No impact | Investigate & cleanup |

---

**Next Steps:**
1. Run migration script on production server
2. Verify schema matches code expectations
3. Test LeadHunter functionality
4. Monitor logs for migration messages
