#!/usr/bin/env python3
"""
Скрипт для начального заполнения контент-плана "Base Expert Pack" (9 постов).

Использование:
    python scripts/seed_base_expert_pack.py

Генерирует 9 постов с фокусом на:
- Доверие (экспертность Юлии, опыт GEORIS)
- Кейсы (московские ЖК: Зиларт, Династия, Символ)
- Регуляции 2026 года (новые правила, изменения в законодательстве)

Все посты сохраняются в content_plan со статусом 'approved' и готовы к публикации.
Канал: GEORIS (корпоративный стиль).
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.creative_agent import CreativeAgent
from database.db import Database

async def seed():
    """Генерирует и сохраняет Base Expert Pack (9 постов) в контент-план."""
    print("🚀 Запуск генерации базового пакета ГЕОРИС...")
    
    # Инициализируем агента и БД
    agent = CreativeAgent()
    db = Database()
    
    # Подключаемся к БД
    await db.connect()
    
    try:
        # Генерируем 9 постов через CreativeAgent
        posts = await agent.generate_base_expert_pack()
        
        if not posts:
            print("❌ Не удалось сгенерировать посты")
            return
        
        print(f"✅ Сгенерировано {len(posts)} постов")
        
        # Сохраняем посты в контент-план
        publish_date = datetime.now() + timedelta(hours=1)  # Первый пост через час
        
        for i, post_data in enumerate(posts, 1):
            try:
                # Извлекаем данные поста
                title = post_data.get("title", f"Пост {i}")
                body = post_data.get("body", "")
                cta = post_data.get("cta", "")
                theme = post_data.get("theme", "base_expert")
                image_prompt = post_data.get("image_prompt", "")
                
                # Сохраняем пост в БД через save_post (создает новую запись)
                post_id = await db.save_post(
                    post_type="expert_pack",
                    title=title,
                    body=body,
                    cta=cta,
                    publish_date=publish_date,
                    channel="georis",  # Корпоративный стиль GEORIS
                    theme=theme,
                    image_url=None,  # Изображение будет сгенерировано при публикации из image_prompt
                    status="approved"
                )
                
                # Обновляем image_prompt через update_content_plan_entry (если есть)
                if image_prompt:
                    await db.update_content_plan_entry(post_id, image_prompt=image_prompt)
                
                print(f"✅ Пост {i} ('{title[:50]}...') успешно добавлен в базу (ID: {post_id}).")
                
                # Увеличиваем дату публикации на 2 часа для следующего поста
                publish_date += timedelta(hours=2)
                
            except Exception as e:
                print(f"❌ Ошибка сохранения поста {i}: {e}")
                continue
        
        print(f"\n✅ Base Expert Pack заполнен: {len(posts)} постов сохранено в контент-план")
        print(f"📅 Первый пост будет опубликован: {publish_date - timedelta(hours=2 * (len(posts) - 1))}")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(seed())
