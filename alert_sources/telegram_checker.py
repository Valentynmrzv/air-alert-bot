import os
import asyncio
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient, events
from dotenv import load_dotenv
# Виправлено: шлях до файлу filter.py та назви функцій
from utils.filter import classify_message
import json

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
client = TelegramClient("/home/vlntnmrzv/air-alert-bot/anon", API_ID, API_HASH)

message_queue = asyncio.Queue()
catch_up_messages = []

with open("alert_sources/channels.json", "r", encoding="utf-8") as f:
    monitored_channels = json.load(f)

@client.on(events.NewMessage(chats=monitored_channels))
async def handle_all_messages(event):
    username = getattr(event.chat, 'username', None)
    if not username:
        return  # Ігноруємо повідомлення без username
    classified = classify_message(event.message.text, f"https://t.me/{username}/{event.message.id}")
    if classified:
        classified["date"] = event.message.date.replace(tzinfo=timezone.utc)
        await message_queue.put(classified)

async def start_monitoring():
    await client.start()
    await client.run_until_disconnected()

async def check_telegram_channels():
    if not message_queue.empty():
        return await message_queue.get()
    return None

async def fetch_last_messages(minutes: int):
    if not await client.is_user_authorized():
        print("❗ Не авторизовано для підвантаження повідомлень.")
        return

    monitor_start_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    print(f"🔄 Підвантаження повідомлень з {monitor_start_time.isoformat()}")

    for username in monitored_channels:
        try:
            entity = await client.get_entity(username)
            messages = await client.get_messages(entity, limit=200)
            for msg in reversed(messages):
                if msg.date.replace(tzinfo=timezone.utc) >= monitor_start_time:
                    classified = classify_message(msg.text, f"https://t.me/{username}/{msg.id}")
                    if classified:
                        classified["date"] = msg.date.replace(tzinfo=timezone.utc)
                        catch_up_messages.append(classified)
        except Exception as e:
            print(f"❌ Помилка підвантаження повідомлень з {username}: {e}")

async def get_catch_up_messages():
    return catch_up_messages