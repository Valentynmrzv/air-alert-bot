import asyncio, os
from telethon import TelegramClient
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
API_ID = int(os.getenv("API_ID")); API_HASH = os.getenv("API_HASH")
SESSION_FILE = (Path(__file__).resolve().parent / "telethon.session").as_posix()

async def main():
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.connect()
    print("AUTHORIZED:", await client.is_user_authorized())
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
