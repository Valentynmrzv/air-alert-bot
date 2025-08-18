import asyncio, os, pyqrcode
from telethon import TelegramClient
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH"))
SESSION_FILE = (Path(__file__).resolve().parent / "telethon.session").as_posix()

async def main():
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.connect()
    qr = await client.qr_login()
    print("\n🔳 Telegram > Налаштування > Пристрої > Підключити пристрій\n")
    print(pyqrcode.create(qr.url, error='L').terminal(quiet_zone=1))
    print("\nПосилання:\n", qr.url)
    await qr.wait()
    print("✅ Сесію збережено у файлі:", SESSION_FILE)
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
