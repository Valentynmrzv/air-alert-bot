import os
import requests
import asyncio

async def send_alert_message(text):
    bot_token = os.getenv("BOT_TOKEN")
    channel_id = os.getenv("CHANNEL_ID")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": channel_id,
        "text": text,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code != 200:
            print(f"❌ Помилка надсилання: {response.status_code} - {response.text}")
        else:
            print(f"✅ Повідомлення надіслано: {text}")
    except Exception as e:
        print(f"❌ Виключення при надсиланні: {e}")
