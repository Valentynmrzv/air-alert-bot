# export_session.py
import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

# якщо файл-сесія називається інакше, підстав сюди правильну назву/шлях
SESSION_FILE = os.getenv("SESSION_PATH", "session")

with TelegramClient(SESSION_FILE, api_id, api_hash) as client:
    if client.is_user_authorized():
        s = client.session.save()  # це StringSession рядок
        print("\n=== TELETHON_SESSION ===")
        print(s)
        print("========================\n")
    else:
        print("❗ Файлова сесія не авторизована. Спочатку запусти authorize.py один раз.")
