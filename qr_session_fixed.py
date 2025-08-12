# qr_session_fixed.py
import asyncio, os
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

async def main():
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()

    qr = await client.qr_login()
    print("\n🔳 Telegram на телефоні → Налаштування → Пристрої → Підключити пристрій")
    print("   Скануй QR або відкрий цей URL у Telegram:\n")
    print(qr.url)

    await qr.wait()  # дочекатись підтвердження!
    ok = await client.is_user_authorized()
    print("Authorized:", ok)
    s = client.session.save()
    print("\n=== TELETHON_SESSION ===")
    print(s)
    print("========================\n")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
