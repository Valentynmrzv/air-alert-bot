# utils/sender.py
import os
import aiohttp
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

async def send_alert_message(text: str, notify: bool = True, chat_id: str | None = None, markdown: bool = True):
    """Надіслати текстове повідомлення. Якщо markdown=False — шлемо plain text (без parse_mode)."""
    target_chat_id = chat_id or CHANNEL_ID
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": target_chat_id,
        "text": text,
        "disable_notification": not notify,
    }
    if markdown:
        data["parse_mode"] = "Markdown"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, timeout=10) as response:
                if response.status != 200:
                    print(f"❌ Помилка надсилання повідомлення: {await response.text()}")
                    return None
                payload = await response.json()
                print("✅ Повідомлення надіслано")
                return payload["result"]["message_id"]
    except Exception as e:
        print(f"❌ Виняток при надсиланні повідомлення: {e}")
        return None

async def send_start_message(start_time: datetime, chat_id: str):
    """Стартове службове повідомлення (Markdown ок)."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    text = format_uptime_message(start_time)
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_notification": True,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, timeout=10) as response:
                if response.status != 200:
                    print(f"❌ Помилка надсилання стартового повідомлення: {await response.text()}")
                    return None
                return (await response.json())["result"]["message_id"]
    except Exception as e:
        print(f"❌ Виняток при надсиланні стартового повідомлення: {e}")
        return None

async def edit_message(message_id: int, start_time: datetime, chat_id: str):
    """Оновлення таймера (Markdown ок)."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    text = format_uptime_message(start_time)
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, timeout=10) as response:
                if response.status != 200:
                    print(f"❌ Помилка оновлення повідомлення: {await response.text()}")
    except Exception as e:
        print(f"❌ Виняток при оновленні повідомлення: {e}")

def format_uptime_message(start_time: datetime) -> str:
    delta = int((datetime.now() - start_time).total_seconds())
    hours = delta // 3600
    minutes = (delta % 3600) // 60
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"🟢 Бот працює без зупинок: {hours} год {minutes} хв\n"
        f"⏱ Запущено: {start_str}\n"
        "Стежу за повітряними тривогами."
    )

async def send_alert_with_screenshot(caption: str, screenshot_path: str, chat_id: str | None = None, markdown: bool = True):
    """Надіслати фото-скріншот із підписом. Якщо markdown=False — шлемо без parse_mode."""
    target_chat_id = chat_id or CHANNEL_ID
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

    try:
        async with aiohttp.ClientSession() as session:
            with open(screenshot_path, "rb") as image:
                data = aiohttp.FormData()
                data.add_field("chat_id", str(target_chat_id))
                data.add_field("photo", image)
                data.add_field("caption", caption)
                if markdown:
                    data.add_field("parse_mode", "Markdown")

                async with session.post(url, data=data, timeout=20) as response:
                    if response.status != 200:
                        print(f"❌ Помилка надсилання скріншота: {await response.text()}")
                    else:
                        print("✅ Скріншот успішно надіслано")
    except Exception as e:
        print(f"❌ Виняток при надсиланні скріншота: {e}")
