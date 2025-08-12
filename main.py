import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv

import alert_sources.telegram_checker as tg_checker
from utils.sender import send_alert_message, send_alert_with_screenshot, send_start_message, edit_message
from utils.screenshot import take_alert_screenshot
from utils.state_manager import load_state, save_state, ensure_state_defaults
from web import server

load_dotenv()

def update_alert_status(active: bool, state: dict, server_status: dict):
    state["alert_active"] = active
    server_status["alert_active"] = active
    save_state(state)
    print(f"[STATUS] alert_active встановлено у {active}")

async def _push_web():
    # невелика обгортка щоб не дублювати виклики
    await server.push_update()

def _ensure_state(state: dict):
    changed = ensure_state_defaults(state, defaults={
        "alert_active": False,
        "threat_sent": [],
        "alert_started_at": {
            "Броварський район": None,
            "Київська область": None
        },
        "start_message_id": None,
        "timer_message_id": None,
        "last_ids": {}
    })
    if changed:
        save_state(state)
    return state

async def monitor_loop(channel_id: int, user_chat_id: int, start_time: datetime):
    state = _ensure_state(load_state())
    alert_active = state.get("alert_active", False)
    threat_sent = set(state.get("threat_sent", []))

    while True:
        msg = await tg_checker.check_telegram_channels()
        if not msg:
            await asyncio.sleep(1)
            continue

        if isinstance(msg.get('date'), datetime):
            msg['date'] = msg['date'].isoformat()

        server.status["messages_received"] += 1
        server.status["last_messages"].append(msg)
        if len(server.status["last_messages"]) > 100:
            server.status["last_messages"] = server.status["last_messages"][-100:]

        district = (msg.get("district") or "").lower()
        text = msg.get("text", "")
        msg_id = msg.get("id")
        threat = msg.get("threat_type")
        src = msg.get("url", "")

        if district not in ["броварський район", "київська область"]:
            await _push_web()
            continue

        # 🚨 Старт тривоги
        if msg["type"] == "alarm" and not alert_active:
            alert_active = True
            threat_sent.clear()
            update_alert_status(True, state, server.status)

            started_map = state.get("alert_started_at", {})
            started_map[district.title()] = datetime.now().isoformat()
            state["alert_started_at"] = started_map
            save_state(state)

            server.status["logs"].append(f"Тривога у {district.title()}: {text[:80]}")
            if len(server.status["logs"]) > 100:
                server.status["logs"] = server.status["logs"][-100:]

            alert_text = (
                f"🚨 *Повітряна тривога* — {district.title()}!\n"
                + (f"• Можлива загроза: *{threat}*\n" if threat else "")
                + (f"• Джерело: {src}\n" if src else "")
                + "Будьте в укриттях."
            )
            screenshot_path = await take_alert_screenshot()
            if screenshot_path:
                await send_alert_with_screenshot(alert_text, screenshot_path, chat_id=channel_id)
            else:
                await send_alert_message(alert_text, notify=True, chat_id=channel_id)

            await _push_web()

        # ✅ Відбій
        elif msg["type"] == "all_clear" and alert_active:
            alert_active = False
            update_alert_status(False, state, server.status)

            duration_str = ""
            started_map = state.get("alert_started_at", {})
            started_iso = started_map.get(district.title())
            if started_iso:
                try:
                    started_dt = datetime.fromisoformat(started_iso)
                    mins = int((datetime.now() - started_dt).total_seconds() // 60)
                    duration_str = f"\n🕒 Небезпека тривала близько {mins} хв"
                except Exception:
                    pass

            started_map[district.title()] = None
            state["alert_started_at"] = started_map
            save_state(state)

            server.status["logs"].append(f"Відбій у {district.title()}: {text[:80]}")
            if len(server.status["logs"]) > 100:
                server.status["logs"] = server.status["logs"][-100:]

            alert_text = f"✅ *Відбій тривоги* — {district.title()}!" + duration_str + (f"\n• Джерело: {src}" if src else "")
            await send_alert_message(alert_text, notify=True, chat_id=channel_id)

            await _push_web()

        # ⚠️ Інфо під час тривоги (без сповіщення)
        elif msg["type"] == "info" and alert_active and msg_id not in threat_sent:
            server.status["logs"].append(f"Новина: {text[:80]}")
            if len(server.status["logs"]) > 100:
                server.status["logs"] = server.status["logs"][-100:]

            info_text = f"⚠️ {text}" + (f"\n• Джерело: {src}" if src else "")
            await send_alert_message(info_text, notify=False, chat_id=channel_id)
            threat_sent.add(msg_id)
            state["threat_sent"] = list(threat_sent)
            save_state(state)

            await _push_web()
        else:
            # на всяк — теж оновимо веб
            await _push_web()

async def uptime_loop(user_chat_id: int, start_time: datetime):
    state = _ensure_state(load_state())

    start_message_id = await send_start_message(start_time, user_chat_id)
    if start_message_id:
        state["start_message_id"] = start_message_id
        save_state(state)

    timer_message_id = await send_alert_message("🕒 Таймер роботи бота: 0 год 0 хв", notify=False, chat_id=user_chat_id)
    if timer_message_id:
        state["timer_message_id"] = timer_message_id
        save_state(state)

    while True:
        await asyncio.sleep(300)
        await edit_message(timer_message_id, start_time, user_chat_id)
        await _push_web()

async def main():
    channel_id = int(os.getenv("CHANNEL_ID"))
    user_chat_id = int(os.getenv("USER_CHAT_ID"))
    start_time = datetime.now()

    # Підключаємось
    await tg_checker.client.connect()

    # Перевіряємо авторизацію без інтерактиву
    if not await tg_checker.client.is_user_authorized():
        print("❗ StringSession невалідний або не авторизований. Онови TELETHON_SESSION у .env")
        return


    # catch-up вимкнено заради економії лімітів
    # await tg_checker.fetch_last_messages(60)

    await server.start_web_server()

    await asyncio.gather(
        tg_checker.start_monitoring(),
        monitor_loop(channel_id, user_chat_id, start_time),
        uptime_loop(user_chat_id, start_time)
    )

if __name__ == "__main__":
    asyncio.run(main())
