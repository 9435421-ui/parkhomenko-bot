import os
import asyncio
import logging
from database.db import Database
from config import VK_API_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CheckLeadHunter")

async def check_vk_token():
    print("\n--- VK TOKEN CHECK ---")
    if not VK_API_TOKEN:
        print("[ERROR] VK_API_TOKEN is missing in .env")
        return
    
    import aiohttp
    url = f"https://api.vk.com/method/groups.getById?access_token={VK_API_TOKEN}&v=5.131"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            if "error" in data:
                print(f"[ERROR] VK Token Error: {data['error']['error_msg']}")
            else:
                print("[OK] VK Token is valid")

async def list_targets():
    print("\n--- ACTIVE TARGETS ---")
    db = Database()
    await db.connect()
    try:
        targets = await db.get_active_targets_for_scout()
        if not targets:
            print("No active targets found in database.")
        for t in targets:
            platform = t.get("platform", "unknown")
            link = t.get("link", "no link")
            title = t.get("title", "no title")
            print(f"[{platform.upper()}] {title} - {link}")
    except Exception as e:
        print(f"[ERROR] Error fetching targets: {e}")
    finally:
        if db.conn:
            await db.conn.close()

async def main():
    await check_vk_token()
    await list_targets()

if __name__ == "__main__":
    asyncio.run(main())
