# qr_session_no_prompt.py
import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

client = TelegramClient(StringSession(), api_id, api_hash)
client.connect()

# НЕ викликаємо client.start()!
qr = client.qr_login()

print("\n🔳 Відкрий Telegram на телефоні:")
print("   Налаштування → Пристрої → Підключити пристрій")
print("   Скануй QR або просто відкрий цей URL у Telegram:\n")
print(qr.url)

# Чекаємо підтвердження на телефоні
qr.wait()

# Після підтвердження друкуємо StringSession
s = client.session.save()
print("\n=== TELETHON_SESSION ===")
print(s)
print("========================\n")

client.disconnect()
