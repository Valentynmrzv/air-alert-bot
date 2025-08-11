# gen_session.py
import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, SendCodeUnavailableError
from dotenv import load_dotenv

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
phone = os.getenv("TELEGRAM_PHONE")

with TelegramClient(StringSession(), api_id, api_hash) as client:
    client.connect()
    if not client.is_user_authorized():
        try:
            client.send_code_request(phone)
        except SendCodeUnavailableError:
            print("⏳ Занадто багато запитів коду. Зачекай 5–15 хв і спробуй ще раз.")
            raise
        code = input("Enter the code you received via Telegram: ")
        try:
            client.sign_in(phone=phone, code=code)
        except SessionPasswordNeededError:
            password = input("Two-step password (if enabled): ")
            client.sign_in(password=password)

    print("\n=== TELETHON_SESSION ===")
    print(client.session.save())
    print("========================\n")
