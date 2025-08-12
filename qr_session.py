# qr_session.py
import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

with TelegramClient(StringSession(), api_id, api_hash) as client:
    # 1) Створюємо QR-логін
    qr = client.qr_login()
    print("\n🔳 Відкрий Telegram на телефоні:")
    print("   Налаштування → Пристрої → Підключити пристрій (Link Desktop Device)")
    print("   Скануй QR, використовуючи вікно, що з'явилось у додатку Telegram.")
    print("\nЯкщо термінал не показує QR-картинку — просто відкрий цей URL у Telegram:\n")
    print(qr.url)  # це посилання Telegram для авторизації через QR

    # 2) Чекаємо, поки ти відскануєш і підтвердиш
    qr.wait()

    # 3) Виводимо StringSession
    s = client.session.save()
    print("\n=== TELETHON_SESSION ===")
    print(s)
    print("========================\n")
    print("✅ Скопіюй цей рядок у .env як TELETHON_SESSION=... (одним рядком)")
