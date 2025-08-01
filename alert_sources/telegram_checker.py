import os
from telethon import TelegramClient, events
from utils.filter import classify_message

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
monitored_channels = os.getenv("MONITORED_CHANNELS", "").split(",")

client = TelegramClient("anon", api_id, api_hash)

alert_queue = []

@client.on(events.NewMessage(chats=monitored_channels))
async def handler(event):
    try:
        text = event.message.message
        message_id = event.message.id
        chat = await event.get_chat()
        username = chat.username or f"c/{chat.id}"
        message_url = f"https://t.me/{username}/{message_id}"

        result = classify_message(text, message_url)
        if result:
            print(f"📥 Нове повідомлення з Telegram: {result}")
            alert_queue.append(result)
    except Exception as e:
        print(f"❌ Помилка обробки повідомлення: {e}")

async def check_telegram_channels():
    if alert_queue:
        return alert_queue.pop(0)
    return None

async def start_monitoring():
    await client.start()
    print("🟢 Telethon запущено і слухає канали...")
    await client.run_until_disconnected()
