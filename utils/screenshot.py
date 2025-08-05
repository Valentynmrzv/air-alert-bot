import os
from playwright.async_api import async_playwright

async def take_alert_screenshot(path="map.png"):
    url = "https://alerts.in.ua/"
    screenshot_path = os.path.join("temp", path)

    os.makedirs("temp", exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url)
        await page.set_viewport_size({"width": 1280, "height": 720})
        await page.screenshot(path=screenshot_path, full_page=True)
        await browser.close()

    return screenshot_path
