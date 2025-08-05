import os
import json
import asyncio
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv
from alert_sources.classifier import classify_message

load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
phone = os.getenv("TELEGRAM_PHONE")

client = TelegramClient('session', api_id, api_hash)
message_queue = asyncio.Queue()

with open("alert_sources/channels.json", "r", encoding="utf-8") as f:
    monitored_channels = set(json.load(f))

@client.on(events.NewMessage())
async def handler(event):
    sender = await event.get_sender()
    if hasattr(sender, 'username') and sender.username in monitored_channels:
        text = event.raw_text
        url = f"https://t.me/{sender.username}/{event.id}"
        classified = classify_message(text, url)

        if classified:
            classified["id"] = event.id
            await message_queue.put(classified)

async def start_monitoring():
    await client.connect()
    if not await client.is_user_authorized():
        # При запуску через systemd — просто повідомляємо, що не авторизовані
        print("❗ Не авторизовано. Будь ласка, запустіть скрипт вручну для первинної авторизації.")
        return
    print("🟢 Telethon запущено і слухає канали...")
    await client.run_until_disconnected()

async def check_telegram_channels():
    try:
        return message_queue.get_nowait()
    except asyncio.QueueEmpty:
        return None
