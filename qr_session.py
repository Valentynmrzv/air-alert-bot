# qr_session.py
import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH"))

async def main():
    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        print("🔳 Зараз з'явиться QR. Відкрий Telegram на телефоні:")
        print("  Налаштування → Пристрої → Підключити пристрій → Скануй QR")
        qr = await client.qr_login()
        print(qr.url)  # якщо TTY не малює ASCII-QR, просто відкрий цей URL з камери/браузера Telegram
        await qr.wait()  # чекаємо поки ти відскануєш і підтвердиш
        print("\n=== TELETHON_SESSION ===")
        print(client.session.save())
        print("========================\n")

if __name__ == "__main__":
    asyncio.run(main())
