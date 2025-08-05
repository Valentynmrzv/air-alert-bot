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
    chrome_options.add_argument("--window-size=900,900")  # квадратне вікно
    chrome_options.add_argument("--disable-gpu")

    service = Service("/usr/bin/chromedriver")

    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(url)

        # Очікуємо повне завантаження
        driver.implicitly_wait(10)

        # Якщо хочеш - можна підкоригувати розмір сторінки, щоб не було дуже великого скріншоту
        total_width = driver.execute_script("return document.body.scrollWidth")
        total_height = driver.execute_script("return document.body.scrollHeight")

        max_size = 900  # максимально 900 пікселів по ширині та висоті

        width = min(total_width, max_size)
        height = min(total_height, max_size)

        driver.set_window_size(width, height)

        driver.save_screenshot(output_path)
        driver.quit()
        print(f"🖼 Скріншот збережено: {output_path}")
        return output_path

    except Exception as e:
        print(f"❌ Помилка при створенні скріншота: {e}")
        return None
