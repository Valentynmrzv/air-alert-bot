import os
import json
import asyncio
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, FloodWaitError
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
        print("❗ Не авторизовано. Будь ласка, запустіть скрипт вручну для первинної авторизації.")
        return
    print("🟢 Telethon запущено і слухає канали...")

    while True:
        try:
            await client.run_until_disconnected()
        except FloodWaitError as e:
            print(f"Отримано FloodWaitError, чекаю {e.seconds} секунд...")
            await asyncio.sleep(e.seconds)

async def check_telegram_channels():
    try:
        return message_queue.get_nowait()
    except asyncio.QueueEmpty:
        return None

async def fetch_last_messages(state, limit=20):
    """
    Завантажує останні повідомлення з усіх каналів для обробки активних тривог при старті.
    """
    for username in monitored_channels:
        try:
            entity = await client.get_entity(username)
            messages = await client.get_messages(entity, limit=limit)
            for message in reversed(messages):  # від старих до нових
                text = message.raw_text
                url = f"https://t.me/{username}/{message.id}"
                classified = classify_message(text, url)
                if classified and classified["id"] not in state.get('sent', []):
                    await message_queue.put(classified)
        except Exception as e:
            print(f"❌ Помилка при завантаженні повідомлень з {username}: {e}")
