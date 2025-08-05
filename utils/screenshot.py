import os
import subprocess
from datetime import datetime

async def take_alert_screenshot():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = "screenshots"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"alert_map_{timestamp}.png")
    url = "https://map.ukrainealarm.com/"

    command = [
        "wkhtmltoimage",
        "--width", "1024",
        "--height", "768",
        url,
        output_path
    ]

    try:
        subprocess.run(command, check=True)
        print(f"🖼 Скріншот збережено: {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"❌ Помилка при створенні скріншота: {e}")
        return None
