from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID = 27661955
API_HASH = "f24f00c4e7aee89b1b1bb53a56fd297a"
SESSION_FILE = "/home/vlntnmrzv/air-alert-bot/session.session"

with TelegramClient(SESSION_FILE, API_ID, API_HASH) as client:
    string = StringSession.save(client.session)
    print("\n=== TELETHON_SESSION ===")
    print(string)
    print("========================\n")
