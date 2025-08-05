import asyncio
from utils.screenshot import take_alert_screenshot

async def test():
    path = await take_alert_screenshot()
    print(f"Screenshot saved to: {path}")

if __name__ == "__main__":
    asyncio.run(test())
