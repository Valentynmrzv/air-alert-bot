import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import alert_sources.telegram_checker as tg_checker
from utils.sender import send_alert_message, send_alert_with_screenshot, send_start_message, edit_message
from utils.screenshot import take_alert_screenshot
from utils.state_manager import load_state, save_state
from web import server  # Імпорт вебсервера з server.py

load_dotenv()

async def monitor_loop(channel_id: int, user_chat_id: int, start_time: datetime):
    state = load_state()
    alert_active = state.get("alert_active", False)
    threat_sent = set(state.get("threat_sent", []))

    print("🚀 Починаємо 'наздоганяючий' режим...")
    catch_up_messages = await tg_checker.get_catch_up_messages()
    catch_up_messages.sort(key=lambda x: x['date'])

    for msg in catch_up_messages:
        district = msg.get("district", "").lower()
        text = msg.get("text", "")
        msg_id = msg.get("id")

        if msg["type"] == "alarm" and not alert_active:
            alert_active = True
            threat_sent.clear()
            print(f"   [CATCH-UP] Активна тривога у {district.title()}.")

        elif msg["type"] == "all_clear" and alert_active:
            alert_active = False
            print(f"   [CATCH-UP] Відбій тривоги у {district.title()}.")

        elif msg["type"] == "info" and alert_active and msg_id not in threat_sent:
            threat_sent.add(msg_id)
            print(f"   [CATCH-UP] Новина під час тривоги: {text[:50]}...")

    state["alert_active"] = alert_active
    state["threat_sent"] = list(threat_sent)
    save_state(state)
    print(f"✅ 'Наздоганяючий' режим завершено. alert_active={alert_active}")

    while True:
        msg = await tg_checker.check_telegram_channels()
        if not msg:
            await asyncio.sleep(1)
            continue

        # --- Оновлюємо лічильник повідомлень для вебпанелі ---
        server.status["messages_received"] += 1

        district = msg.get("district", "").lower()
        text = msg.get("text", "")
        msg_id = msg.get("id")

        if district not in ["броварський район", "київська область"]:
            continue

        if msg["type"] == "alarm" and not alert_active:
            alert_active = True
            threat_sent.clear()
            state["alert_active"] = alert_active
            state["threat_sent"] = list(threat_sent)
            save_state(state)

            server.status["alert_active"] = True
            server.status["logs"].append(f"Тривога у {district.title()}: {text[:50]}")

            alert_text = f"🚨 Повітряна тривога у {district.title()}!"
            screenshot_path = await take_alert_screenshot()
            if screenshot_path:
                await send_alert_with_screenshot(alert_text, screenshot_path, chat_id=channel_id)
            else:
                print(f"Sending alert to channel {channel_id}: {alert_text}")
                await send_alert_message(alert_text, chat_id=channel_id)

        elif msg["type"] == "all_clear" and alert_active:
            alert_active = False
            state["alert_active"] = alert_active
            state["threat_sent"] = list(threat_sent)
            save_state(state)

            server.status["alert_active"] = False
            server.status["logs"].append(f"Відбій у {district.title()}: {text[:50]}")

            alert_text = f"✅ Відбій тривоги у {district.title()}!"
            print(f"Sending alert to channel {channel_id}: {alert_text}")
            await send_alert_message(alert_text, chat_id=channel_id)

        elif msg["type"] == "info" and alert_active and msg_id not in threat_sent:
            server.status["logs"].append(f"Новина: {text[:50]}")
            await send_alert_message(f"⚠️ {text}", notify=False, chat_id=channel_id)
            threat_sent.add(msg_id)
            state["threat_sent"] = list(threat_sent)
            save_state(state)


async def uptime_loop(user_chat_id: int, start_time: datetime):
    state = load_state()

    # При кожному запуску створюємо нове стартове повідомлення
    start_message_id = await send_start_message(start_time, user_chat_id)
    if start_message_id:
        state["start_message_id"] = start_message_id
        save_state(state)

    # При кожному запуску створюємо нове повідомлення з таймером
    timer_message_id = await send_alert_message("🕒 Таймер роботи бота: 0 год 0 хв", notify=False, chat_id=user_chat_id)
    if timer_message_id:
        state["timer_message_id"] = timer_message_id
        save_state(state)

    while True:
        await asyncio.sleep(300)  # оновлюємо кожні 5 хвилин
        await edit_message(timer_message_id, start_time, user_chat_id)


async def main():
    channel_id = int(os.getenv("CHANNEL_ID"))
    user_chat_id = int(os.getenv("USER_CHAT_ID"))
    start_time = datetime.now()

    # Підключаємо клієнта без запиту телефону (бо сесія збережена)
    await tg_checker.client.start()

    if not await tg_checker.client.is_user_authorized():
        print("❗ Не авторизовано. Запусти authorize.py для первинної авторизації.")
        return

    # Підвантажуємо останні повідомлення для "наздоганяючого" старту
    await tg_checker.fetch_last_messages(60)

    # Запускаємо вебсервер
    await server.start_web_server()

    # Запускаємо асинхронно всі цикли
    await asyncio.gather(
        tg_checker.start_monitoring(),
        monitor_loop(channel_id, user_chat_id, start_time),
        uptime_loop(user_chat_id, start_time)
    )


if __name__ == "__main__":
    asyncio.run(main())
