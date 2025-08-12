# qr_session_no_prompt.py
import os
import asyncio
import qrcode_terminal
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

async def main():
    # Створюємо клієнт з пустим StringSession
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()

    # Генеруємо QR
    qr_login = await client.qr_login()

    print("\n🔳 Відкрий Telegram на телефоні:")
    print("   Налаштування → Пристрої → Підключити пристрій")
    print("\nСкануй цей QR у терміналі:\n")
    qrcode_terminal.draw(qr_login.url)

    print("\nАбо відкрий це посилання в Telegram:")
    print(qr_login.url)

    # Чекаємо підтвердження
    await qr_login.wait()

    # Зберігаємо StringSession
    s = client.session.save()
    print("\n=== TELETHON_SESSION ===")
    print(s)
    print("========================\n")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
