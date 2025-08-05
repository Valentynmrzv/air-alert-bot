import os
import requests
from datetime import datetime
import asyncio
import time

_last_uptime_text = None  # глобальна змінна

async def send_alert_message(text, notify=True, chat_id=None):
    bot_token = os.getenv("BOT_TOKEN")
    if chat_id is None:
        chat_id = os.getenv("CHANNEL_ID")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_notification": not notify
    }

    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 10))
            print(f"❗ FloodWaitError: чекаю {retry_after} секунд перед повтором...")
            await asyncio.sleep(retry_after)
            return await send_alert_message(text, notify, chat_id)
        elif response.status_code != 200:
            print(f"❌ Помилка надсилання: {response.text}")
            return None
        else:
            message_id = response.json()["result"]["message_id"]
            print(f"✅ Повідомлення надіслано, message_id: {message_id}")
            return message_id
    except Exception as e:
        print(f"❌ Виняток при надсиланні: {e}")
        return None

async def send_start_message(start_time, chat_id):
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
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 10))
            print(f"❗ FloodWaitError: чекаю {retry_after} секунд перед повтором стартового повідомлення...")
            await asyncio.sleep(retry_after)
            return await send_start_message(start_time, chat_id)
        elif response.status_code == 200:
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
        return

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
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 10))
            print(f"❗ FloodWaitError: чекаю {retry_after} секунд перед оновленням повідомлення...")
            await asyncio.sleep(retry_after)
            await edit_message(start_time, message_id, chat_id)
        elif response.status_code != 200:
            print(f"❌ Помилка оновлення повідомлення: {response.text}")
        else:
            print("ℹ️ Повідомлення оновлено")
    except Exception as e:
        print(f"❌ Виняток при оновленні повідомлення: {e}")

def format_uptime_message(start_time):
    delta = int((datetime.now() - start_time).total_seconds())
    hours = delta // 3600
    minutes = (delta % 3600) // 60
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"🟢 Бот працює без зупинок: {hours} год {minutes} хв\n"
        f"⏱ Запущено: {start_str}\n"
        "Стежу за повітряними тривогами..."
    )

async def send_alert_with_screenshot(caption, screenshot_path, chat_id=None):
    bot_token = os.getenv("BOT_TOKEN")
    if chat_id is None:
        chat_id = os.getenv("CHANNEL_ID")

    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"

    with open(screenshot_path, "rb") as image:
        files = {"photo": image}
        data = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "Markdown"
        }

        try:
            response = requests.post(url, data=data, files=files, timeout=10)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 10))
                print(f"❗ FloodWaitError: чекаю {retry_after} секунд перед повтором надсилання фото...")
                await asyncio.sleep(retry_after)
                return await send_alert_with_screenshot(caption, screenshot_path, chat_id)
            elif response.status_code != 200:
                print(f"❌ Помилка надсилання фото: {response.text}")
                return None
            else:
                print("📸 Скріншот надіслано з повідомленням")
                message_id = response.json()["result"]["message_id"]
                return message_id
        except Exception as e:
            print(f"❌ Виняток при надсиланні скріншоту: {e}")
            return None
