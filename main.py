import asyncio
from dotenv import load_dotenv
from alert_sources.telegram_checker import check_telegram_channels, start_monitoring
from utils.sender import send_alert_message
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

            if "тривога" in text.lower() and msg_id not in state['sent']:
                message = f"🚨 *Повітряна тривога!*\n📍 {district}"
                await send_alert_message(message)
                state['sent'].append(msg_id)
                alert_active = True
                save_state(state)

            elif threat and msg_id not in threat_sent:
                message = f"🔻 *Тип загрози:* {threat}\n📍 {district}\n[Джерело]({link})"
                await send_alert_message(message)
                threat_sent.add(msg_id)

            elif "відбій" in text.lower() and msg_id not in state['sent']:
                message = f"✅ *Відбій тривоги.*\n📍 {district}"
                await send_alert_message(message)
                state['sent'].append(msg_id)
                alert_active = False
                threat_sent.clear()
                save_state(state)

        await asyncio.sleep(2)

async def main():
    await asyncio.gather(
        start_monitoring(),
        monitor_loop()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("⛔ Зупинено вручну.")
