import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

async def take_alert_screenshot():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = "screenshots"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"alert_{timestamp}.png")
    url = "https://alerts.in.ua/"

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1280,720")
    chrome_options.add_argument("--disable-gpu")

    # Вкажи шлях до chromedriver явно
    service = Service("/usr/bin/chromedriver")

    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(url)

        # Можна почекати, якщо потрібно, щоб сторінка повністю завантажилась
        driver.implicitly_wait(10)

        # Зробити скріншот повної сторінки
        driver.save_screenshot(output_path)
        driver.quit()
        print(f"🖼 Скріншот збережено: {output_path}")
        return output_path

    except Exception as e:
        print(f"❌ Помилка при створенні скріншота: {e}")
        return None
