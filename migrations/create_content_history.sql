-- Content History table for financial tracking
-- Хранение текста: 3 месяца
-- Хранение метаданных: 12 месяцев

CREATE TABLE IF NOT EXISTS content_history (
    id SERIAL PRIMARY KEY,
    post_text TEXT,               -- Удаляем через 3 месяца
    image_url TEXT,               -- Ссылка на S3/файл
    model_used VARCHAR(50),       -- Nano Banana / Yandex ART
    cost_rub DECIMAL(10, 2),      -- Для финансового отчета
    platform VARCHAR(20),         -- TG или VK
    channel VARCHAR(50),          -- TERION, DOM_GRAD, VK
    post_id INTEGER,              -- Ссылка на original post
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Для очистки
    is_archived BOOLEAN DEFAULT FALSE -- Пометка для статистики
);

-- Индекс для быстрой очистки по дате
CREATE INDEX IF NOT EXISTS idx_content_history_created_at ON content_history(created_at);

-- Индекс для финансовой отчетности
CREATE INDEX IF NOT EXISTS idx_content_history_model_used ON content_history(model_used);
CREATE INDEX IF NOT EXISTS idx_content_history_cost_rub ON content_history(cost_rub);
