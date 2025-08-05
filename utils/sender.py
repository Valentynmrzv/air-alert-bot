import os
import requests
from datetime import datetime

_last_uptime_text = None  # глобальна змінна

async def send_alert_message(text, silent=False):
    bot_token = os.getenv("BOT_TOKEN")
    channel_id = os.getenv("CHANNEL_ID")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": channel_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_notification": silent  # ← додано
    }

    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code != 200:
            print(f"❌ Помилка надсилання: {response.text}")
        else:
            print(f"✅ Повідомлення надіслано")
    except Exception as e:
        print(f"❌ Виняток при надсиланні: {e}")

async def send_start_message(start_time, chat_id) -> int:
    bot_token = os.getenv("BOT_TOKEN")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    text = format_uptime_message(start_time)
    global _last_uptime_text
    _last_uptime_text = text

    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            message_id = response.json()["result"]["message_id"]
            print(f"✅ Бот запущено, message_id: {message_id}")
            return message_id
        else:
            print(f"❌ Помилка стартового повідомлення: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Виняток при надсиланні стартового повідомлення: {e}")
        return None

async def edit_message(start_time, message_id, chat_id):
    global _last_uptime_text
    new_text = format_uptime_message(start_time)

    if new_text == _last_uptime_text:
        return  # нічого не змінювати

    _last_uptime_text = new_text

    bot_token = os.getenv("BOT_TOKEN")
    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"

    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": new_text,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code != 200:
            print(f"❌ Помилка оновлення повідомлення: {response.text}")
        else:
            print("ℹ️ Повідомлення оновлено")
    except Exception as e:
        print(f"❌ Виняток при оновленні повідомлення: {e}")

def format_uptime_message(start_time):
    delta = int((datetime.now() - start_time).total_seconds())
    hours = delta // 3600
    minutes = (delta % 3600) // 60
    return f"🟢 Бот працює без зупинок: {hours} год {minutes} хв\nСтежу за повітряними тривогами..."
