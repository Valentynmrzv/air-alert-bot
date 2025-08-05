import os
import json
import asyncio
from telethon import TelegramClient, events
from dotenv import load_dotenv
from alert_sources.classifier import classify_message

load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

client = TelegramClient('session', api_id, api_hash)
message_queue = asyncio.Queue()

# Завантажити список каналів
with open("alert_sources/channels.json", "r", encoding="utf-8") as f:
    monitored_channels = set(json.load(f))

# --- Обробка нових повідомлень ---
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

# --- Ініціалізація Telethon ---
async def start_monitoring():
    await client.start()
    print("🟢 Telethon запущено і слухає канали...")
    await client.run_until_disconnected()

# --- Отримання повідомлень з черги ---
async def check_telegram_channels():
    try:
        return message_queue.get_nowait()
    except asyncio.QueueEmpty:
        return None
