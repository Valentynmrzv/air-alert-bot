import asyncio
from datetime import datetime
from dotenv import load_dotenv
from alert_sources.telegram_checker import check_telegram_channels, start_monitoring
from utils.state_manager import load_state, save_state
from utils.screenshot import take_alert_screenshot
from utils.sender import send_alert_message, send_start_message, edit_message, send_alert_with_screenshot
import os

load_dotenv()

async def monitor_loop(channel_id):
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

            if "тривога" in text.lower() and msg_id not in state['sent']:
                message = f"🚨 *Повітряна тривога!*\n📍 {district}"
                screenshot_path = await take_alert_screenshot()
                try:
                    await send_alert_with_screenshot(message, screenshot_path, chat_id=channel_id)
                except Exception as e:
                    print(f"❌ Помилка надсилання тривоги: {e}")
                state['sent'].append(msg_id)
                alert_active = True
                save_state(state)

            elif "відбій" in text.lower() and msg_id not in state['sent']:
                message = f"✅ *Відбій тривоги.*\n📍 {district}"
                try:
                    await send_alert_message(message, notify=True, chat_id=channel_id)
                except Exception as e:
                    print(f"❌ Помилка надсилання відбою: {e}")
                state['sent'].append(msg_id)
                alert_active = False
                threat_sent.clear()
                save_state(state)

            elif alert_active and msg_id not in threat_sent:
                try:
                    if threat:
                        message = f"🔻 *Тип загрози:* {threat}\n📍 {district}\n[Джерело]({link})"
                        await send_alert_message(message, notify=False, chat_id=channel_id)
                    else:
                        message = f"ℹ️ {text}\n[Джерело]({link})"
                        await send_alert_message(message, notify=False, chat_id=channel_id)
                    threat_sent.add(msg_id)
                except Exception as e:
                    print(f"❌ Помилка надсилання додаткової інформації: {e}")

        await asyncio.sleep(2)


async def main():
    start_time = datetime.now()
    user_chat_id = os.getenv("USER_CHAT_ID")
    channel_id = os.getenv("CHANNEL_ID")

    state = load_state()

    if "start_message_id" not in state or state["start_message_id"] is None:
        start_message_id = await send_start_message(start_time, user_chat_id)
        if start_message_id is None:
            print("❌ Не вдалося відправити стартове повідомлення, завершуємо.")
            return
        state["start_message_id"] = start_message_id
        save_state(state)
    else:
        start_message_id = state["start_message_id"]

    if "timer_message_id" not in state or state["timer_message_id"] is None:
        timer_message_id = await send_alert_message("🕒 Таймер роботи бота: 0 год 0 хв", notify=False, chat_id=user_chat_id)
        if timer_message_id is None:
            print("❌ Не вдалося відправити таймер, завершуємо.")
            return
        state["timer_message_id"] = timer_message_id
        save_state(state)
    else:
        timer_message_id = state["timer_message_id"]

    async def update_status():
        while True:
            if timer_message_id:
                try:
                    await edit_message(start_time, timer_message_id, user_chat_id)
                except Exception as e:
                    print(f"❌ Помилка оновлення статусного повідомлення: {e}")
            await asyncio.sleep(1800)

    await asyncio.gather(
        start_monitoring(),
        monitor_loop(channel_id),
        update_status()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("⛔ Зупинено вручну.")
