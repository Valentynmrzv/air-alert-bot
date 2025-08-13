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

# Два дозволені регіони
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

    while True:
        msg = await tg_checker.check_telegram_channels()
        if not msg:
            await asyncio.sleep(1)
            continue

        # нормалізуємо дату для статусу
        if isinstance(msg.get("date"), datetime):
            msg["date"] = msg["date"].isoformat()

        server.status["messages_received"] += 1
        server.status["last_messages"].append(msg)
        if len(server.status["last_messages"]) > 100:
            server.status["last_messages"] = server.status["last_messages"][-100:]

        district = (msg.get("district") or "").lower().strip()
        text = msg.get("text", "") or ""
        msg_id = msg.get("id")
        source_url = (msg.get("url") or "").strip()  # уже правильний air_alert_ua
        threat = msg.get("threat_type")
        region_hit = bool(msg.get("region_hit"))   # з чекера
        rapid_hit = bool(msg.get("rapid_hit"))     # з чекера
        revisor_bonus = bool(msg.get("revisor_bonus"))  # ✓ додано

        # ---------- ALARM / ALL_CLEAR (офіційні події вже відфільтровані в чекері) ----------
        if msg["type"] in ("alarm", "all_clear"):
            # працюємо лише з нашими регіонами
            if district not in ALLOWED_DISTRICTS:
                continue

            # Старт тривоги
            if msg["type"] == "alarm" and not alert_active:
                alert_active = True
                threat_sent.clear()
                update_alert_status(True, state, server.status)

                server.status["logs"].append(
                    f"Тривога у {district.title()}: {text[:120]}"
                )
                if len(server.status["logs"]) > 100:
                    server.status["logs"] = server.status["logs"][-100:]

                alert_text = (
                    f"🚨 Повітряна тривога — {district.title()}!\n"
                    + (f"• Можлива загроза: {threat}\n" if threat else "")
                    + (f"• Джерело: {source_url}\n" if source_url else "")
                    + "Будьте в укриттях."
                )
                screenshot_path = await take_alert_screenshot()
                if screenshot_path:
                    await send_alert_with_screenshot(
                        alert_text, screenshot_path, chat_id=channel_id
                    )
                else:
                    # Markdown тут безпечний (текст контрольований)
                    await send_alert_message(
                        alert_text, notify=True, chat_id=channel_id, parse_mode="Markdown"
                    )

            # Відбій
            elif msg["type"] == "all_clear" and alert_active:
                alert_active = False
                update_alert_status(False, state, server.status)

                server.status["logs"].append(
                    f"Відбій у {district.title()}: {text[:120]}"
                )
                if len(server.status["logs"]) > 100:
                    server.status["logs"] = server.status["logs"][-100:]

                alert_text = (
                    f"✅ Відбій тривоги — {district.title()}!\n"
                    + (f"• Джерело: {source_url}" if source_url else "")
                )
                await send_alert_message(
                    alert_text, notify=True, chat_id=channel_id, parse_mode="Markdown"
                )

            state["threat_sent"] = list(threat_sent)
            save_state(state)
            continue

        # ---------- INFO ПІД ЧАС ТРИВОГИ ----------
        # Під час активної тривоги шлемо в канал info, якщо:
        #   - є наші GEO (region_hit), АБО
        #   - це швидка загроза (rapid_hit: балістика/МіГ/пуск), АБО
        #   - це короткий апдейт від bro_revisor (revisor_bonus).
        if msg["type"] == "info" and alert_active and msg_id not in threat_sent:
            if region_hit or rapid_hit or revisor_bonus:
                server.status["logs"].append(f"Новина: {text[:160]}")
                if len(server.status["logs"]) > 100:
                    server.status["logs"] = server.status["logs"][-100:]

                # ВАЖЛИВО: без parse_mode — не ламаємо сирі URL з підкресленнями
                forward_text = f"⚠️ {text}"
                if source_url:
                    forward_text += f"\n• Джерело: {source_url}"
                await send_alert_message(
                    forward_text, notify=False, chat_id=channel_id, parse_mode=None
                )

                threat_sent.add(msg_id)
                state["threat_sent"] = list(threat_sent)
                save_state(state)
            else:
                # діагностика чому пропущено
                why = []
                if not region_hit:
                    why.append("нема GEO")
                if not rapid_hit:
                    why.append("нема RAPID")
                if not revisor_bonus:
                    why.append("нема REVISOR")
                server.status["logs"].append(
                    f"Пропущено info ({', '.join(why)}): {text[:120]}"
                )
                if len(server.status["logs"]) > 100:
                    server.status["logs"] = server.status["logs"][-100:]


async def uptime_loop(user_chat_id: int, start_time: datetime):
    state = load_state()

    start_message_id = await send_start_message(start_time, user_chat_id)
    if start_message_id:
        state["start_message_id"] = start_message_id
        save_state(state)

    timer_message_id = await send_alert_message(
        "🕒 Таймер роботи бота: 0 год 0 хв",
        notify=False,
        chat_id=user_chat_id,
        parse_mode="Markdown",
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
            print("Онови TELETHON_SESSION у .env (QR/генератор сесії).")
            return

    # catch-up вимкнено (економія лімітів)
    # await tg_checker.fetch_last_messages(60)

    await server.start_web_server()

    await asyncio.gather(
        tg_checker.start_monitoring(),
        monitor_loop(channel_id, user_chat_id, start_time),
        uptime_loop(user_chat_id, start_time),
    )


if __name__ == "__main__":
    asyncio.run(main())
