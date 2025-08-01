import asyncio
from dotenv import load_dotenv
from alert_sources.news_checker import check_news_sources
from utils.sender import send_alert_message
from utils.state_manager import load_state, save_state

load_dotenv()

async def main():
    state = load_state()

    while True:
        print("🔄 Перевірка джерел...")

        news_result = await check_news_sources()

        if news_result:
            alert_text = news_result['text']
            source_url = news_result['url']
            district = news_result.get('district', 'невідомо')
            threat_type = news_result.get('threat_type', 'невідомо')

            alert_id = news_result['id']
            if alert_id not in state['sent']:
                state['sent'].append(alert_id)
                save_state(state)

                message = f"🚨 *Повітряна тривога*\n📍 {district}\n🔻 Загроза: {threat_type}\n[Джерело]({source_url})"
                await send_alert_message(message)

        await asyncio.sleep(60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("⛔ Зупинено вручну.")
