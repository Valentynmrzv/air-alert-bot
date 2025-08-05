import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

    service = Service("/usr/bin/chromedriver")

    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(url)

        wait = WebDriverWait(driver, 15)  # чекати максимум 15 секунд

        # Очікуємо, що на сторінці з'явиться елемент карти
        # Потрібно замінити селектор на актуальний з сайту
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div#map")))

        # Розширюємо розмір вікна до повного розміру сторінки для скріншоту
        total_width = driver.execute_script("return document.body.scrollWidth")
        total_height = driver.execute_script("return document.body.scrollHeight")
        driver.set_window_size(total_width, total_height)

        # Робимо скріншот
        driver.save_screenshot(output_path)
        driver.quit()
        print(f"🖼 Скріншот збережено: {output_path}")
        return output_path

    except Exception as e:
        print(f"❌ Помилка при створенні скріншота: {e}")
        return None
