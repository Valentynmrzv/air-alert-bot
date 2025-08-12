# export_session.py
import os
from pathlib import Path
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Завантажуємо .env
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

# Визначаємо шлях до файл-сесії:
# 1) Якщо задано SESSION_PATH у .env — використовуємо його
# 2) Інакше якщо існує session.session у корені — беремо його
# 3) Інакше беремо "session" у корені
session_path = os.getenv("SESSION_PATH")
if not session_path:
    if (BASE_DIR / "session.session").exists():
        session_path = str(BASE_DIR / "session.session")
    else:
        session_path = str(BASE_DIR / "session")

print(f"[EXPORT] Using file session at: {session_path}")

with TelegramClient(session_path, api_id, api_hash) as client:
    if not client.is_user_authorized():
        raise SystemExit("❗ Файлова сесія не авторизована. Запусти один раз authorize.py, потім повтори export.")
    s = StringSession.save(client.session)
    print("\n=== TELETHON_SESSION ===")
    print(s)
    print("========================\n")
    print("✅ Скопіюй цей рядок у .env як TELETHON_SESSION=... (одним рядком)")
