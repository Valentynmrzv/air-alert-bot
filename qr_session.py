# qr_session.py
import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

# Тут обов'язково StringSession(), щоб не питало номер
with TelegramClient(StringSession(), api_id, api_hash) as client:
    qr = client.qr_login()
    print("\n🔳 Відкрий Telegram на телефоні:")
    print("   Налаштування → Пристрої → Підключити пристрій")
    print("   Скануй QR або натисни на цей URL у Telegram:\n")
    print(qr.url)

    qr.wait()  # чекаємо, поки підтвердиш

    s = client.session.save()
    print("\n=== TELETHON_SESSION ===")
    print(s)
    print("========================\n")
