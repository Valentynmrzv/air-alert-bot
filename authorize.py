import os, asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
phone = os.getenv("TELEGRAM_PHONE")
string = os.getenv("TELETHON_SESSION")

client = TelegramClient(StringSession(string) if string else "session", api_id, api_hash)

async def main():
    await client.connect()
    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        code = input("Enter the code you received via Telegram: ")
        try:
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            password = input("Two-step verification enabled. Enter your password: ")
            await client.sign_in(password=password)
        # Якщо генерували без TEELTHON_SESSION, вивести його:
        if not string and isinstance(client.session, StringSession):
            print("\n=== TELETHON_SESSION ===")
            print(client.session.save())
            print("========================\n")
    print("✅ Авторизація пройшла успішно!")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
