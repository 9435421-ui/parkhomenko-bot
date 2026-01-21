-- Миграция: добавление таблицы для хранения состояний пользователей
-- Дата: 2026-01-21
-- Автор: Comet + VS Code AI

CREATE TABLE IF NOT EXISTS user_states (
    user_id INTEGER PRIMARY KEY,
    state_data TEXT NOT NULL,
    consent_data TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Индекс для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_user_states_updated
ON user_states(updated_at DESC);
