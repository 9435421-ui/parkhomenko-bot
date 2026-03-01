import asyncio
import sys
import os
sys.path.insert(0, '.')
import aiosqlite

async def get_vk_groups():
    db_path = os.path.abspath(os.getenv('DATABASE_PATH', 'database/bot.db'))
    print(f'Podkluchenie k BD: {db_path}')
    
    if not os.path.exists(db_path):
        print(f'Baza dannyh ne naydena: {db_path}')
        return
    
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """SELECT link, title, geo_tag, is_high_priority, platform 
               FROM target_resources 
               WHERE (platform='vk' OR link LIKE '%vk.com%') 
               AND status='active'
               ORDER BY title"""
        )
        rows = await cursor.fetchall()
        
        if not rows:
            print('\n[!] V baze net aktivnyh VK-grupp dlya monitoringa.')
            print('    Dobavte gruppy cherez /add_target ili /spy_discover')
        else:
            print(f'\n[+] Naydeno VK-grupp: {len(rows)}\n')
            print('='*70)
            for r in rows:
                link = r['link'] or 'N/A'
                title = r['title'] or 'Bez nazvaniya'
                geo = r['geo_tag'] or 'ne ukazan'
                priority = 'HIGH' if r['is_high_priority'] else 'normal'
                platform = r['platform'] or 'unknown'
                print(f'\n* {title}')
                print(f'  Link: {link}')
                print(f'  Platform: {platform}')
                print(f'  Geo: {geo}')
                print(f'  Priority: {priority}')
            print('='*70)

if __name__ == '__main__':
    asyncio.run(get_vk_groups())
