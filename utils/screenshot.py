import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

async def take_alert_screenshot():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"screenshots/alert_{timestamp}.png"
    url = "https://map.ukrainealarm.com/"

    os.makedirs("screenshots", exist_ok=True)

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,720")

    driver = webdriver.Chrome(options=options)
    driver.get(url)

    # Почекаємо 5 секунд, щоб сторінка завантажилась
    driver.implicitly_wait(5)

    driver.save_screenshot(output_path)
    driver.quit()

    print(f"🖼 Скріншот збережено: {output_path}")
    return output_path
