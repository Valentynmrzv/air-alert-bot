# main.py
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv

import alert_sources.telegram_checker as tg_checker
from utils.sender import (
    send_alert_message,
    send_alert_with_screenshot,
    send_start_message,
    edit_message,
)
from utils.screenshot import take_alert_screenshot
from utils.state_manager import load_state, save_state
from web import server

load_dotenv()

ALLOWED_DISTRICTS = {"броварський район", "київська область"}

def update_alert_status(active: bool, state: dict, server_status: dict):
    state["alert_active"] = active
    server_status["alert_active"] = active
    save_state(state)
    print(f"[STATUS] alert_active встановлено у {active}")

async def monitor_loop(channel_id: int, user_chat_id: int, start_time: datetime):
    state = load_state()
    alert_active = state.get("alert_active", False)
    threat_sent = set(state.get("threat_sent", []))

    print("🚀 Починаємо 'наздоганяючий' режим.")
    catch_up_messages = await tg_checker.get_catch_up_messages()

    # Конвертуємо дату у рядок, щоб уникнути проблем з JSON серіалізацією
    for msg in catch_up_messages:
        if isinstance(msg.get("date"), datetime):
            msg["date"] = msg["date"].isoformat()

    catch_up_messages.sort(key=lambda x: x["date"])

    for msg in catch_up_messages:
        district = (msg.get("district") or "").lower()
        text = msg.get("text", "")
        msg_id = msg.get("id")

        if msg["type"] == "alarm" and not alert_active:
            alert_active = True
            threat_sent.clear()
            update_alert_status(True, state, server.status)
            print(f"   [CATCH-UP] Активна тривога у {district.title()}.")

        elif msg["type"] == "all_clear" and alert_active:
            alert_active = False
            update_alert_status(False, state, server.status)
            print(f"   [CATCH-UP] Відбій тривоги у {district.title()}.")

        elif msg["type"] == "info" and alert_active and msg_id not in threat_sent:
            threat_sent.add(msg_id)
            print(f"   [CATCH-UP] Новина під час тривоги: {text[:50]}.")

    state["threat_sent"] = list(threat_sent)
    save_state(state)
    update_alert_status(alert_active, state, server.status)

    while True:
        msg = await tg_checker.check_telegram_channels()
        if not msg:
            await asyncio.sleep(1)
            continue

        # Конвертація дати в ISO-рядок перед додаванням в статус
        if isinstance(msg.get("date"), datetime):
            msg["date"] = msg["date"].isoformat()

        server.status["messages_received"] += 1
        server.status["last_messages"].append(msg)
        if len(server.status["last_messages"]) > 100:
            server.status["last_messages"] = server.status["last_messages"][-100:]

        district = (msg.get("district") or "").lower()
        text = msg.get("text", "")
        msg_id = msg.get("id")
        source_url = (msg.get("url") or "").strip() or "https://t.me/air_alert_ua"
        threat = msg.get("threat_type")  # може бути None

        # =========================
        # ALARM/ALL_CLEAR: тільки для наших регіонів
        # =========================
        if msg["type"] in ("alarm", "all_clear"):
            if district not in ALLOWED_DISTRICTS:
                continue

            if msg["type"] == "alarm" and not alert_active:
                alert_active = True
                threat_sent.clear()
                update_alert_status(True, state, server.status)

                server.status["logs"].append(
                    f"Тривога у {district.title()}: {text[:80]}"
                )
                if len(server.status["logs"]) > 100:
                    server.status["logs"] = server.status["logs"][-100:]

                alert_text = (
                    f"🚨 Повітряна тривога — {district.title()}!\n"
                    + (f"• Можлива загроза: {threat}\n" if threat else "")
                    + f"• Джерело: {source_url}\n"
                    + "Будьте в укриттях."
                )
                screenshot_path = await take_alert_screenshot()
                if screenshot_path:
                    await send_alert_with_screenshot(
                        alert_text, screenshot_path, chat_id=channel_id
                    )
                else:
                    await send_alert_message(alert_text, chat_id=channel_id)

            elif msg["type"] == "all_clear" and alert_active:
                alert_active = False
                update_alert_status(False, state, server.status)

                server.status["logs"].append(
                    f"Відбій у {district.title()}: {text[:80]}"
                )
                if len(server.status["logs"]) > 100:
                    server.status["logs"] = server.status["logs"][-100:]

                alert_text = (
                    f"✅ Відбій тривоги — {district.title()}!\n"
                    f"• Джерело: {source_url}"
                )
                await send_alert_message(alert_text, chat_id=channel_id)

            # перехід до наступного повідомлення
            continue

        # =========================
        # INFO: під час активної тривоги — завжди пересилаємо,
        #       незалежно від district (може бути None)
        # =========================
        if msg["type"] == "info" and alert_active and msg_id not in threat_sent:
            server.status["logs"].append(f"Новина: {text[:80]}")
            if len(server.status["logs"]) > 100:
                server.status["logs"] = server.status["logs"][-100:]

            info_text = f"⚠️ {text}" + (f"\n• Джерело: {source_url}" if source_url else "")
            await send_alert_message(info_text, notify=False, chat_id=channel_id)
            threat_sent.add(msg_id)
            state["threat_sent"] = list(threat_sent)
            save_state(state)

async def uptime_loop(user_chat_id: int, start_time: datetime):
    state = load_state()

    start_message_id = await send_start_message(start_time, user_chat_id)
    if start_message_id:
        state["start_message_id"] = start_message_id
        save_state(state)

    timer_message_id = await send_alert_message(
        "🕒 Таймер роботи бота: 0 год 0 хв", notify=False, chat_id=user_chat_id
    )
    if timer_message_id:
        state["timer_message_id"] = timer_message_id
        save_state(state)

    while True:
        await asyncio.sleep(300)
        await edit_message(timer_message_id, start_time, user_chat_id)

async def main():
    channel_id = int(os.getenv("CHANNEL_ID"))
    user_chat_id = int(os.getenv("USER_CHAT_ID"))
    start_time = datetime.now()

    await tg_checker.client.connect()

    if not await tg_checker.client.is_user_authorized():
        try:
            await tg_checker.client.start()
        except Exception as e:
            print(f"❗ Не авторизовано: {e}")
            print("Запусти QR/генератор сесії, щоб оновити TELETHON_SESSION у .env")
            return

    # catch-up вимкнено, щоб менше навантажувати API
    # await tg_checker.fetch_last_messages(60)

    await server.start_web_server()

    await asyncio.gather(
        tg_checker.start_monitoring(),
        monitor_loop(channel_id, user_chat_id, start_time),
        uptime_loop(user_chat_id, start_time),
    )

if __name__ == "__main__":
    asyncio.run(main())
