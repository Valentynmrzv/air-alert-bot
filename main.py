from dotenv import load_dotenv
load_dotenv()

import os
import time
import requests
import asyncio
from bs4 import BeautifulSoup
import threading
from flask import Flask, jsonify
import requests

start_time = time.time()
last_ping_time = time.time()

# --- Flask вебсервер ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Бот активний 🟢"

@app.route("/status")
def status():
    uptime = round(time.time() - start_time)
    last_ping_age = round(time.time() - last_ping_time)
    return jsonify({
        "status": "ok",
        "uptime_seconds": uptime,
        "seconds_since_last_ping": last_ping_age
    })

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# --- Відправка повідомлення в Telegram ---
def send_telegram_message(text, image_url=None):
    try:
        bot_token = os.environ.get("BOT_TOKEN")
        channel_id = os.environ.get("CHANNEL_ID")

        if image_url:
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            data = {
                "chat_id": channel_id,
                "caption": text,
                "photo": image_url
            }
        else:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                "chat_id": channel_id,
                "text": text
            }

        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            return True
        else:
            print(f"Помилка відправки: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Помилка при відправці повідомлення: {e}")
        return False

# --- Повідомлення про активність бота ---
def send_ping_to_user():
    global last_ping_time
    try:
        bot_token = os.environ.get("BOT_TOKEN")
        user_chat_id = os.environ.get("USER_CHAT_ID")
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": user_chat_id,
            "text": "🟢 Бот активний"
        }
        requests.post(url, data=data, timeout=10)
        last_ping_time = time.time()
    except Exception as e:
        print(f"Помилка при надсиланні ping-повідомлення: {e}")


# --- Перевірка тривоги по області ---
def check_region_alert(region_name="Київська область"):
    try:
        r = requests.get("https://alerts.in.ua/api/states", timeout=10)
        r.raise_for_status()
        data = r.json()

        for item in data:
            if item.get("name") == region_name:
                return item.get("alert", False)

        print(f"⚠️ Область '{region_name}' не знайдена.")
        return False

    except Exception as e:
        print(f"❌ Помилка при запиті області: {e}")
        return False

# --- Універсальна перевірка тривоги по громаді/району/місту ---
def check_air_alert(name="Броварська територіальна громада"):
    try:
        url = "https://alerts.in.ua/api/states"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        for item in data:
            if item.get("name") == name:
                return item.get("alert", False)

        print(f"⚠️ Не знайдено об'єкта з назвою: {name}")
        return False

    except Exception as e:
        print(f"❌ Помилка при перевірці тривоги для {name}: {e}")
        return False

# --- Основна логіка бота ---
async def main():
    bot_token = os.environ.get("BOT_TOKEN")
    channel_id = os.environ.get("CHANNEL_ID")
    user_chat_id = os.environ.get("USER_CHAT_ID")

    if not bot_token:
        print("❌ BOT_TOKEN не встановлено")
        return
    if not channel_id:
        print("❌ CHANNEL_ID не встановлено")
        return
    if not user_chat_id:
        print("❌ USER_CHAT_ID не встановлено")
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={"chat_id": user_chat_id, "text": "🧪 Бот запущено!"}
        )
    except Exception as e:
        print(f"Помилка при надсиланні тестового повідомлення: {e}")

    region_alert = check_region_alert()
    brovary_alert = check_air_alert()

    if region_alert or brovary_alert:
        parts = []
        if brovary_alert:
            parts.append("📍 *Броварський район*")
        if region_alert:
            parts.append("📍 *Київська область*")
        msg = "🚨 Повітряна тривога!\n" + "\n".join(parts)
        send_telegram_message(
            text=msg,
            image_url="https://image.thum.io/get/width/800/crop/700/fullpage/https://alerts.in.ua/"
        )
        print("🔔 Повідомлення про активну тривогу надіслано одразу після запуску")

    last_status = {"region": region_alert, "brovary": brovary_alert}
    ping_interval = 3600

    while True:
        try:
            region_alert = check_region_alert()
            brovary_alert = check_air_alert("Броварський район")

            alert_now = {"region": region_alert, "brovary": brovary_alert}

            if alert_now != last_status:
                if region_alert or brovary_alert:
                    parts = []
                    if brovary_alert:
                        parts.append("📍 *Броварський район*")
                    if region_alert:
                        parts.append("📍 *Київська область*")
                    msg = "🚨 Повітряна тривога!\n" + "\n".join(parts)
                else:
                    msg = "✅ Відбій тривоги."

                send_telegram_message(
                    text=msg,
                    image_url="https://image.thum.io/get/width/800/crop/700/fullpage/https://alerts.in.ua/"
                )
                print(f"🔔 Сповіщення надіслано: {msg}")
                last_status = alert_now

            if time.time() - last_ping_time > ping_interval:
                send_ping_to_user()

            await asyncio.sleep(30)

        except Exception as e:
            print(f"Помилка в основному циклі: {e}")
            await asyncio.sleep(60)

# --- Запуск Flask і нескінченний цикл з перезапуском бота ---
if __name__ == "__main__":
    print("🔎 Перевірка тривоги вручну:")
    print("Броварський район:", check_air_alert("Броварський район"))

    # flask_thread = threading.Thread(target=run_flask)
    # flask_thread.daemon = True
    # flask_thread.start()

    # while True:
    #     try:
    #         asyncio.run(main())
    #     except Exception as e:
    #         print(f"❌ Бот впав. Перезапуск через 5 секунд... {e}")
    #         time.sleep(5)
