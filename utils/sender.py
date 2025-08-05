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

async def send_start_message(start_time) -> int:
    bot_token = os.getenv("BOT_TOKEN")
    channel_id = os.getenv("CHANNEL_ID")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    data = {
        "chat_id": channel_id,
        "text": format_uptime_message(start_time),
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            message_id = response.json()["result"]["message_id"]
            print(f"✅ Бот запущено, message_id: {message_id}")
            return message_id
        else:
            print(f"❌ Помилка надсилання стартового повідомлення: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Виняток при стартовому повідомленні: {e}")
        return None

async def edit_message(start_time, message_id):
    bot_token = os.getenv("BOT_TOKEN")
    channel_id = os.getenv("CHANNEL_ID")
    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"

    data = {
        "chat_id": channel_id,
        "message_id": message_id,
        "text": format_uptime_message(start_time),
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code != 200:
            print(f"❌ Помилка оновлення повідомлення: {response.text}")
    except Exception as e:
        print(f"❌ Виняток при оновленні повідомлення: {e}")

def format_uptime_message(start_time):
    from datetime import datetime
    delta = int((datetime.now() - start_time).total_seconds())
    hours = delta // 3600
    minutes = (delta % 3600) // 60
    return f"🟢 Бот працює без зупинок: {hours} год {minutes} хв\nСтежу за повітряними тривогами..."
