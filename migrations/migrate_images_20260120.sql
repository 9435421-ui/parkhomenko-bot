-- Добавление полей для хранения промптов и URL изображений
ALTER TABLE content_plan ADD COLUMN image_prompt TEXT DEFAULT NULL;
ALTER TABLE content_plan ADD COLUMN image_url TEXT DEFAULT NULL;
