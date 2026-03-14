# Database Audit Summary

## Quick Fix Guide

### Critical Issues Found

1. **❌ `spy_leads` table missing on production**
   - **Impact:** LeadHunter cannot save discovered leads
   - **Fix:** Run migration script (see below)

2. **⚠️ Missing columns in `spy_leads`**
   - Missing: `pain_stage`, `priority_score`, `contacted_at`, `sent_to_hot_leads`
   - **Impact:** Features broken (scheduler summaries, hot leads detection)
   - **Fix:** Migration script adds these automatically

3. **⚠️ Import from legacy file**
   - **Fixed:** Updated `run_all.py` to use new structure

---

## Quick Fix: Run Migration Script

**On production server:**

```bash
cd ~/PARKHOMENKO_BOT
python migrations/sync_production_schema.py
```

This script will:
- ✅ Create missing tables (`spy_leads`, `users`, `user_states`, etc.)
- ✅ Add missing columns to existing tables
- ✅ Initialize default data
- ✅ Verify schema integrity

**Safe to run multiple times** - checks before altering.

---

## Verification

After running migration, verify:

```sql
-- Check spy_leads table exists
SELECT name FROM sqlite_master WHERE type='table' AND name='spy_leads';

-- Check required columns exist
PRAGMA table_info(spy_leads);
-- Should show: pain_stage, priority_score, contacted_at, sent_to_hot_leads
```

---

## Full Report

See `docs/DATABASE_AUDIT_REPORT.md` for complete details.
