import asyncio
import os
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def clean_old_screenshots(folder="screenshots", days=1):
    now = time.time()
    cutoff = now - days * 86400

    if not os.path.exists(folder):
        print(f"Папка {folder} не існує")
        return

    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        if os.path.isfile(filepath):
            file_mtime = os.path.getmtime(filepath)
            if file_mtime < cutoff:
                os.remove(filepath)
                print(f"Видалено старий файл: {filepath}")


def take_alert_screenshot_sync():
    clean_old_screenshots()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = "screenshots"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"alert_{timestamp}.png")
    url = "https://alerts.in.ua/"

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=900,900")
    chrome_options.add_argument("--disable-gpu")

    service = Service("/usr/bin/chromedriver")
    driver = None

    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(12)
        driver.get(url)
        driver.implicitly_wait(3)

        total_width = driver.execute_script("return document.body.scrollWidth")
        total_height = driver.execute_script("return document.body.scrollHeight")

        max_size = 900
        width = min(total_width, max_size)
        height = min(total_height, max_size)
        driver.set_window_size(width, height)

        driver.save_screenshot(output_path)
        print(f"Скріншот збережено: {output_path}")
        return output_path
    except Exception as e:
        print(f"Помилка при створенні скріншота: {e}")
        return None
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


async def take_alert_screenshot():
    return await asyncio.to_thread(take_alert_screenshot_sync)
