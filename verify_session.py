# verify_session.py
import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
s = (os.getenv("TELETHON_SESSION") or "").strip()

print("Session length:", len(s))
assert s, "TELETHON_SESSION is empty"

with TelegramClient(StringSession(s), api_id, api_hash) as client:
    print("Authorized:", client.is_user_authorized())
    if client.is_user_authorized():
        me = client.get_me()
        print("Logged in as:", getattr(me, "username", None) or me.id)
