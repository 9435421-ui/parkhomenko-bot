-- =============================================
-- Автоматическая очистка content_history
-- Запускать через Cron / Job Scheduler
-- =============================================

-- === 3 МЕСЯЦА: Удаляем только тексты (оставляем цифры для статистики) ===
-- Выполнять: каждый день в 3:00 MSK
UPDATE content_history 
SET post_text = NULL 
WHERE created_at < datetime('now', '-3 months')
AND post_text IS NOT NULL;


-- === 12 МЕСЯЦЕВ: Полное удаление записей ===
-- Вынимать: раз в месяц (1-го числа)
DELETE FROM content_history 
WHERE created_at < datetime('now', '-12 months');
