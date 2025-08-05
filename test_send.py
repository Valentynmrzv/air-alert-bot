import asyncio
import os
from utils.sender import send_alert_with_screenshot, send_alert_message
from utils.screenshot import take_alert_screenshot

async def test_alert():
    # 1. Звичайне повідомлення без скріншоту
    await send_alert_message("✅ *Тест відбою тривоги.*\n📍 Броварський район", notify=True)

    # 2. Тривога зі скріншотом
    message = "🚨 *Тест тривоги!*\n📍 Броварський район"
    screenshot_path = await take_alert_screenshot()
    await send_alert_with_screenshot(message, screenshot_path)

    # 3. Повідомлення без звуку
    await send_alert_message("ℹ️ Тестове повідомлення без сповіщення", notify=False)

if __name__ == "__main__":
    asyncio.run(test_alert())
