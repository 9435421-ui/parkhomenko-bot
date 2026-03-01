# -*- coding: utf-8 -*-
"""
Скрипт миграции для добавления колонки updated_at в таблицу target_resources
если она отсутствует.
"""
import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiosqlite
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_and_add_updated_at_column(db_path: str = "database/bot.db"):
    """
    Проверяет наличие колонки updated_at в таблице target_resources
    и добавляет её, если отсутствует.
    """
    # Проверяем существование файла БД
    if not os.path.exists(db_path):
        logger.warning(f"⚠️ База данных {db_path} не найдена. Она будет создана при первом запуске бота.")
        return
    
    try:
        async with aiosqlite.connect(db_path) as conn:
            cursor = await conn.cursor()
            
            # Проверяем структуру таблицы target_resources
            await cursor.execute("PRAGMA table_info(target_resources)")
            columns = await cursor.fetchall()
            
            # Получаем список имен колонок
            column_names = [col[1] for col in columns]
            
            logger.info(f"📋 Текущие колонки в target_resources: {', '.join(column_names)}")
            
            # Проверяем наличие колонки updated_at
            if 'updated_at' not in column_names:
                logger.info("🔧 Колонка updated_at отсутствует. Добавляю...")
                
                # Добавляем колонку updated_at
                await cursor.execute("""
                    ALTER TABLE target_resources 
                    ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                """)
                
                # Обновляем существующие записи, устанавливая updated_at = created_at
                # (если created_at существует) или текущее время
                try:
                    await cursor.execute("""
                        UPDATE target_resources 
                        SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP)
                        WHERE updated_at IS NULL
                    """)
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось обновить существующие записи: {e}")
                
                await conn.commit()
                logger.info("✅ Колонка updated_at успешно добавлена в таблицу target_resources")
            else:
                logger.info("✅ Колонка updated_at уже существует в таблице target_resources")
            
            # Проверяем также другие таблицы, которые могут использовать updated_at
            tables_to_check = ['spy_leads', 'content_plan', 'users']
            for table_name in tables_to_check:
                try:
                    await cursor.execute(f"PRAGMA table_info({table_name})")
                    table_columns = await cursor.fetchall()
                    table_column_names = [col[1] for col in table_columns]
                    
                    if 'updated_at' not in table_column_names:
                        logger.info(f"🔧 Добавляю updated_at в таблицу {table_name}...")
                        await cursor.execute(f"""
                            ALTER TABLE {table_name} 
                            ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        """)
                        try:
                            await cursor.execute(f"""
                                UPDATE {table_name} 
                                SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP)
                                WHERE updated_at IS NULL
                            """)
                        except Exception:
                            pass
                        await conn.commit()
                        logger.info(f"✅ Колонка updated_at добавлена в {table_name}")
                    else:
                        logger.debug(f"✅ Колонка updated_at уже есть в {table_name}")
                except Exception as e:
                    logger.debug(f"⚠️ Таблица {table_name} не существует или ошибка проверки: {e}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке/добавлении колонки updated_at: {e}")
        raise


async def main():
    """Главная функция"""
    # Пробуем разные возможные пути к БД
    possible_paths = [
        "database/bot.db",
        "database/terion.db",
        "terion.db",
        "bot.db"
    ]
    
    db_found = False
    for db_path in possible_paths:
        if os.path.exists(db_path):
            logger.info(f"📂 Найдена база данных: {db_path}")
            await check_and_add_updated_at_column(db_path)
            db_found = True
            break
    
    if not db_found:
        logger.warning("⚠️ База данных не найдена ни по одному из путей:")
        for path in possible_paths:
            logger.warning(f"   - {path}")
        logger.info("💡 База данных будет создана автоматически при первом запуске бота.")


if __name__ == "__main__":
    asyncio.run(main())
