import os
import sys
import asyncio
import argparse
from telethon import TelegramClient
from config import API_ID, API_HASH

SESSION_NAME = "anton_parser"

async def check_session():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()
    is_auth = await client.is_user_authorized()
    await client.disconnect()
    return is_auth

async def create_session(reset=False):
    session_file = f"{SESSION_NAME}.session"
    if reset and os.path.exists(session_file):
        os.remove(session_file)
        print(f"🗑️ Session file {session_file} removed.")

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    print("✅ Session created successfully!")
    me = await client.get_me()
    print(f"👤 Authorized as: {me.first_name} (@{me.username})")
    await client.disconnect()

def main():
    parser = argparse.ArgumentParser(description="Telegram Session Manager")
    parser.add_argument("--reset", action="store_true", help="Force recreate session")
    parser.add_argument("--check", action="store_true", help="Check if session is valid")
    args = parser.parse_args()

    if args.check:
        is_valid = asyncio.run(check_session())
        if is_valid:
            print("✅ Session is valid")
            sys.exit(0)
        else:
            print("❌ Session is invalid or not found")
            sys.exit(1)
    
    asyncio.run(create_session(reset=args.reset))

if __name__ == "__main__":
    main()
