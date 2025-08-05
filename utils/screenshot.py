import os
import subprocess
from datetime import datetime

async def take_alert_screenshot():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"screenshots/alert_{timestamp}.png"
    url = "https://alerts.in.ua/"

    os.makedirs("screenshots", exist_ok=True)

    command = [
    "wkhtmltoimage",
    "--width", "1024",
    "--height", "768",  # Фіксована висота
    "--disable-smart-width",
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
