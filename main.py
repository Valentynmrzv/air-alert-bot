import asyncio
from datetime import datetime
from dotenv import load_dotenv
import os

from alert_sources.telegram_checker import check_telegram_channels, start_monitoring
from utils.sender import send_alert_message, send_start_message, edit_message
from utils.state_manager import load_state, save_state

load_dotenv()

async def monitor_loop():
    state = load_state()
    alert_active = False
    threat_sent = set()

    while True:
        result = await check_telegram_channels()

        if result:
            text = result['text']
            link = result['url']
            msg_id = result['id']
            district = result.get('district', 'Броварський район')
            threat = result.get('threat_type')

            # 1. Повітряна тривога (зі звуком)
            if "тривога" in text.lower() and msg_id not in state['sent']:
                message = f"🚨 *Повітряна тривога!*\n📍 {district}"
                await send_alert_message(message, silent=False)
                state['sent'].append(msg_id)
                alert_active = True
                save_state(state)

            # 2. Тип загрози (без звуку)
            elif threat and msg_id not in threat_sent:
                message = f"🔻 *Тип загрози:* {threat}\n📍 {district}\n[Джерело]({link})"
                await send_alert_message(message, silent=True)
                threat_sent.add(msg_id)

            # 3. Відбій тривоги (зі звуком)
            elif "відбій" in text.lower() and msg_id not in state['sent']:
                message = f"✅ *Відбій тривоги.*\n📍 {district}"
                await send_alert_message(message, silent=False)
                state['sent'].append(msg_id)
                alert_active = False
                threat_sent.clear()
                save_state(state)

        await asyncio.sleep(2)

async def main():
    start_time = datetime.now()
    user_chat_id = os.getenv("USER_CHAT_ID")
    message_id = await send_start_message(start_time, user_chat_id)

    async def update_status():
        while True:
            if message_id:
                await edit_message(start_time, message_id, user_chat_id)
            await asyncio.sleep(3600)  # оновлення щогодини

    await asyncio.gather(
        start_monitoring(),   # Telethon слухає повідомлення
        monitor_loop(),       # Бот аналізує чергу
        update_status()       # Щогодинне оновлення повідомлення про аптайм
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("⛔ Зупинено вручну.")
