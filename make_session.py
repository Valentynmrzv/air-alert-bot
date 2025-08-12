# make_session.py
import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, SendCodeUnavailableError
from dotenv import load_dotenv

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
phone = os.getenv("TELEGRAM_PHONE")  # або введеш вручну, якщо немає

with TelegramClient(StringSession(), api_id, api_hash) as client:
    # якщо TELEGRAM_PHONE не задано, запитаємо
    if not phone:
        phone = input("Phone (e.g. +380...): ").strip()
    try:
        client.send_code_request(phone)
    except SendCodeUnavailableError:
        print("⏳ Забагато запитів коду. Почекай 5–15 хв і спробуй знову.")
        raise

    code = input("Enter the code you received: ").strip()
    try:
        client.sign_in(phone=phone, code=code)
    except SessionPasswordNeededError:
        pwd = input("Two-step password (if enabled): ").strip()
        client.sign_in(password=pwd)

    s = client.session.save()
    print("\n=== TELETHON_SESSION ===")
    print(s)
    print("========================\n")
    print("✅ Скопіюй цей рядок у .env як TELETHON_SESSION=...")
