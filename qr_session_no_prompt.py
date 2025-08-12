# qr_session_no_prompt.py
import os
import asyncio
import pyqrcode
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
env_path = ".env"

async def main():
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()

    qr_login = await client.qr_login()
    url = qr_login.url

    print("\n🔳 Відкрий Telegram на телефоні:")
    print("   Налаштування → Пристрої → Підключити пристрій\n")
    # ASCII-QR у терміналі (без Pillow)
    qr = pyqrcode.create(url, error='L')
    print(qr.terminal(quiet_zone=1))

    print("\nАбо просто відкрий це посилання в Telegram:")
    print(url)

    # Дочекатися підтвердження
    await qr_login.wait()

    # Зберегти StringSession
    session_str = client.session.save()
    print("\n=== TELETHON_SESSION ===")
    print(session_str)
    print("========================\n")

    # Оновити/створити .env із TELETHON_SESSION
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    updated = False
    for i, line in enumerate(lines):
        if line.startswith("TELETHON_SESSION="):
            lines[i] = f"TELETHON_SESSION={session_str}\n"
            updated = True
            break
    if not updated:
        lines.append(f"TELETHON_SESSION={session_str}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"[✅] TELETHON_SESSION записано у {env_path}")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
