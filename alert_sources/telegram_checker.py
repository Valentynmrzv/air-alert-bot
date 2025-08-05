import os
import json
import asyncio
from telethon import TelegramClient, events
from dotenv import load_dotenv

load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

client = TelegramClient('session', api_id, api_hash)
message_queue = asyncio.Queue()

# Завантажити список каналів
with open("alert_sources/channels.json", "r") as f:
    monitored_channels = set(json.load(f))

# --- Визначення типу загрози ---
def detect_threat(text):
    lower = text.lower()
    if "шахед" in lower:
        return "Шахеди"
    elif "ракета" in lower:
        return "Ракети"
    elif "баліст" in lower:
        return "Балістика"
    return None

# --- Обробка нових повідомлень ---
@client.on(events.NewMessage())
async def handler(event):
    sender = await event.get_sender()
    if hasattr(sender, 'username') and sender.username in monitored_channels:
        text = event.raw_text
        threat_type = detect_threat(text)

        await message_queue.put({
            "text": text,
            "id": event.id,
            "url": f"https://t.me/{sender.username}/{event.id}",
            "threat_type": threat_type,
            "district": "Броварський район"  # можеш змінити логіку, якщо треба
        })

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
