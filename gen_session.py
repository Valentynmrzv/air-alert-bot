# gen_session.py
import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
phone = os.getenv("TELEGRAM_PHONE")

with TelegramClient(StringSession(), api_id, api_hash) as client:
    client.send_code_request(phone)
    code = input("Enter the code you received via Telegram: ")
    try:
        client.sign_in(phone, code)
    except Exception:
        password = input("Two-step password (if enabled): ")
        client.sign_in(password=password)
    print("\n=== TELETHON_SESSION ===")
    print(client.session.save())
    print("========================\n")
