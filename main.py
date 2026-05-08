import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv
from telethon.errors import (
    AuthKeyError,
    FloodWaitError,
    PhoneMigrateError,
    SessionRevokedError,
    UserMigrateError,
)

import alert_sources.telegram_checker as tg_checker
from utils.screenshot import take_alert_screenshot
from utils.sender import (
    edit_message,
    send_alert_message,
    send_alert_with_screenshot,
    send_start_message,
)
from utils.state_manager import load_state, save_state
from web import server

load_dotenv()

ALLOWED_DISTRICTS = {"броварський район", "київська область"}


def update_alert_status(active: bool, state: dict, server_status: dict):
    state["alert_active"] = active
    server_status["alert_active"] = active
    save_state(state)
    print(f"[STATUS] alert_active set to {active}")


async def send_alarm_screenshot_followup(alert_text: str, channel_id: int):
    screenshot_path = await take_alert_screenshot()
    if screenshot_path:
        await send_alert_with_screenshot(alert_text, screenshot_path, chat_id=channel_id)


async def monitor_loop(channel_id: int, user_chat_id: int, start_time: datetime):
    state = load_state()
    alert_active = state.get("alert_active", False)
    threat_sent = set(state.get("threat_sent", []))
    
    # Використовуємо список для збереження порядку і set для швидкого пошуку
    situation_list = state.get("situation_sent", [])
    situation_sent = set(situation_list)

    while True:
        msg = await tg_checker.check_telegram_channels()
        if not msg:
            await asyncio.sleep(1)
            continue

        if isinstance(msg.get("date"), datetime):
            msg["date"] = msg["date"].isoformat()

        server.status["messages_received"] += 1
        server.status["last_messages"].append(msg)
        if len(server.status["last_messages"]) > 100:
            server.status["last_messages"] = server.status["last_messages"][-100:]

        district = (msg.get("district") or "").lower().strip()
        text = msg.get("text", "") or ""
        msg_id = msg.get("id")
        source_url = (msg.get("url") or "").strip()
        threat = msg.get("threat_type")
        region_hit = bool(msg.get("region_hit"))
        rapid_hit = bool(msg.get("rapid_hit"))
        revisor_bonus = bool(msg.get("revisor_bonus"))
        situation_source = msg.get("situation_source")

        if msg["type"] in ("alarm", "all_clear"):
            if district not in ALLOWED_DISTRICTS:
                continue

            if msg["type"] == "alarm" and not alert_active:
                alert_active = True
                threat_sent.clear()
                update_alert_status(True, state, server.status)

                server.status["logs"].append(f"Тривога у {district.title()}: {text[:120]}")
                if len(server.status["logs"]) > 100:
                    server.status["logs"] = server.status["logs"][-100:]

                # HTML форматування
                alert_text = (
                    f"🚨 <b>Повітряна тривога — {district.title()}!</b>\n"
                    + (f"• Можлива загроза: {threat}\n" if threat else "")
                    + (f"• <a href='{source_url}'>Джерело</a>\n" if source_url else "")
                    + "Будьте в укриттях."
                )

                await send_alert_message(
                    alert_text,
                    notify=True,
                    chat_id=channel_id,
                    parse_mode="HTML",
                )
                asyncio.create_task(send_alarm_screenshot_followup(alert_text, channel_id))

            elif msg["type"] == "all_clear" and alert_active:
                alert_active = False
                update_alert_status(False, state, server.status)

                server.status["logs"].append(f"Відбій у {district.title()}: {text[:120]}")
                if len(server.status["logs"]) > 100:
                    server.status["logs"] = server.status["logs"][-100:]

                # HTML форматування
                alert_text = (
                    f"✅ <b>Відбій тривоги — {district.title()}!</b>\n"
                    + (f"• <a href='{source_url}'>Джерело</a>" if source_url else "")
                )
                await send_alert_message(
                    alert_text,
                    notify=True,
                    chat_id=channel_id,
                    parse_mode="HTML",
                )

            state["threat_sent"] = list(threat_sent)
            save_state(state)
            continue

        if msg["type"] == "situation" and msg_id not in situation_sent:
            server.status["logs"].append(f"Обстановка: {text[:160]}")
            if len(server.status["logs"]) > 100:
                server.status["logs"] = server.status["logs"][-100:]

            prefix = "📡 Обстановка"
            # Перевіряємо обидва
            if situation_source in {"ukraine_pyxx", "cyyiiv_naorym"}:
                prefix = "🔹 Зведення"

            forward_text = f"{prefix}\n\n{text}"
            if source_url:
                forward_text += f"\n\nДжерело: {source_url}"

            await send_alert_message(
                forward_text,
                notify=False,
                chat_id=channel_id,
                parse_mode=None,
            )

            # Захист від переповнення файлу state.json
            situation_list.append(msg_id)
            if len(situation_list) > 50:
                situation_list = situation_list[-50:]  # Залишаємо тільки останні 50
            
            situation_sent = set(situation_list)
            state["situation_sent"] = situation_list
            save_state(state)
            continue

        if msg["type"] == "info" and alert_active and msg_id not in threat_sent:
            if region_hit or rapid_hit or revisor_bonus:
                server.status["logs"].append(f"Новина: {text[:160]}")
                if len(server.status["logs"]) > 100:
                    server.status["logs"] = server.status["logs"][-100:]

                forward_text = f"⚠️ {text}"
                if source_url:
                    forward_text += f"\n• Джерело: {source_url}"

                await send_alert_message(
                    forward_text,
                    notify=False,
                    chat_id=channel_id,
                    parse_mode=None,
                )

                threat_sent.add(msg_id)
                state["threat_sent"] = list(threat_sent)
                save_state(state)
            else:
                why = []
                if not region_hit:
                    why.append("нема GEO")
                if not rapid_hit:
                    why.append("нема RAPID")
                if not revisor_bonus:
                    why.append("нема REVISOR")
                server.status["logs"].append(f"Пропущено info ({', '.join(why)}): {text[:120]}")
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


async def heartbeat_loop():
    while True:
        try:
            if not tg_checker.client.is_connected():
                await asyncio.sleep(5)
                continue
            await tg_checker.client.get_me()
        except Exception as e:
            print(f"Heartbeat failed: {e}")
        await asyncio.sleep(60)


async def run_client_forever():
    tg_2fa_password = os.getenv("TG_2FA_PASSWORD", "")
    backoff = 5

    while True:
        try:
            print("Starting Telegram client...")
            await tg_checker.client.start(password=(tg_2fa_password or None))
            print("Client started. Waiting for disconnect...")
            await tg_checker.start_monitoring()
        except (SessionRevokedError, AuthKeyError) as e:
            print(f"Session/auth error: {e}. Потрібна повторна авторизація.")
            await asyncio.sleep(60)
        except (PhoneMigrateError, UserMigrateError) as e:
            print(f"DC migration: {e}. Перепідключення...")
            await asyncio.sleep(5)
        except FloodWaitError as e:
            print(f"FloodWait {e.seconds}s")
            await asyncio.sleep(e.seconds + 5)
        except Exception as e:
            print(f"Unexpected client error: {e}. Перезапуск через {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
        else:
            backoff = 5


async def main():
    channel_id = int(os.getenv("CHANNEL_ID"))
    user_chat_id = int(os.getenv("USER_CHAT_ID"))
    start_time = datetime.now()

    await server.start_web_server()

    await asyncio.gather(
        run_client_forever(),
        monitor_loop(channel_id, user_chat_id, start_time),
        uptime_loop(user_chat_id, start_time),
        heartbeat_loop(),
    )

if __name__ == "__main__":
    asyncio.run(main())