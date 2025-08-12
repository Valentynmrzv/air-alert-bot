# qr_session_no_prompt.py
import os
import asyncio
import qrcode_terminal
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
env_path = ".env"  # шлях до .env

async def main():
    # Підключення з пустим StringSession
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()

    # Генеруємо QR для входу
    qr_login = await client.qr_login()

    print("\n🔳 Відкрий Telegram на телефоні:")
    print("   Налаштування → Пристрої → Підключити пристрій")
    print("\nСкануй цей QR у терміналі:\n")
    qrcode_terminal.draw(qr_login.url)

    print("\nАбо відкрий це посилання в Telegram:")
    print(qr_login.url)

    # Чекаємо підтвердження входу
    await qr_login.wait()

    # Зберігаємо сесію
    session_str = client.session.save()
    print("\n=== TELETHON_SESSION ===")
    print(session_str)
    print("========================\n")

    # Читаємо існуючий .env і оновлюємо TELETHON_SESSION
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

        print(f"[✅] TELETHON_SESSION оновлено у {env_path}")
    else:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"TELETHON_SESSION={session_str}\n")
        print(f"[✅] Створено {env_path} з TELETHON_SESSION")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
