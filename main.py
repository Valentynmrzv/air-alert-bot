# main.py
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from telethon.errors import (
    AuthKeyError, SessionRevokedError, FloodWaitError,
    PhoneMigrateError, UserMigrateError
)

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

                alert_text = (
                    f"🚨 Повітряна тривога — {district.title()}!\n"
                    + (f"• Можлива загроза: {threat}\n" if threat else "")
                    + (f"• Джерело: {source_url}\n" if source_url else "")
                    + "Будьте в укриттях."
                )
                screenshot_path = await take_alert_screenshot()
                if screenshot_path:
                    await send_alert_with_screenshot(alert_text, screenshot_path, chat_id=channel_id)
                else:
                    await send_alert_message(alert_text, notify=True, chat_id=channel_id, parse_mode="Markdown")

            elif msg["type"] == "all_clear" and alert_active:
                alert_active = False
                update_alert_status(False, state, server.status)

                server.status["logs"].append(f"Відбій у {district.title()}: {text[:120]}")
                if len(server.status["logs"]) > 100:
                    server.status["logs"] = server.status["logs"][-100:]

                alert_text = f"✅ Відбій тривоги — {district.title()}!\n" + (f"• Джерело: {source_url}" if source_url else "")
                await send_alert_message(alert_text, notify=True, chat_id=channel_id, parse_mode="Markdown")

            state["threat_sent"] = list(threat_sent)
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
                await send_alert_message(forward_text, notify=False, chat_id=channel_id, parse_mode=None)

                threat_sent.add(msg_id)
                state["threat_sent"] = list(threat_sent)
                save_state(state)
            else:
                why = []
                if not region_hit:   why.append("нема GEO")
                if not rapid_hit:    why.append("нема RAPID")
                if not revisor_bonus:why.append("нема REVISOR")
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
    """Перевірка «живості» сесії, щоб не помічати дисконект лише під час подій."""
    while True:
        try:
            await tg_checker.client.get_me()
        except Exception as e:
            print(f"💔 Heartbeat failed: {e}")
        await asyncio.sleep(60)

async def run_client_forever():
    """Наглядовий цикл: старт клієнта, очікування, автоперезапуск з бекофом."""
    TG_2FA_PASSWORD = os.getenv("TG_2FA_PASSWORD", "")
    backoff = 5
    while True:
        try:
            print("🔌 Starting Telegram client…")
            await tg_checker.client.start(password=(TG_2FA_PASSWORD or None))
            print("✅ Client started. Waiting for disconnect…")
            await tg_checker.start_monitoring()  # run_until_disconnected()
        except (SessionRevokedError, AuthKeyError) as e:
            print(f"❗ Session revoked/auth key error: {e}. Потрібна повторна авторизація (QR/код + пароль).")
            # Тут варто прислати тобі сповіщення в адмін-чат
            await asyncio.sleep(60)
        except (PhoneMigrateError, UserMigrateError) as e:
            # Telethon сам має хендлити міграцію DC, але на всяк випадок дамо паузу
            print(f"➡️ DC migration: {e}. Перепідключення…")
            await asyncio.sleep(5)
        except FloodWaitError as e:
            print(f"⏳ FloodWait {e.seconds}s — сплю…")
            await asyncio.sleep(e.seconds + 5)
        except Exception as e:
            print(f"⚠️ Unexpected client error: {e}. Перезапуск через {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)  # експоненційний бекоф до 60с
        else:
            # Нормальний вихід (рідко): обнуляємо бекоф
            backoff = 5

async def main():
    channel_id = int(os.getenv("CHANNEL_ID"))
    user_chat_id = int(os.getenv("USER_CHAT_ID"))
    start_time = datetime.now()

    await server.start_web_server()

    await asyncio.gather(
        run_client_forever(),                      # ← наглядовий цикл клієнта
        monitor_loop(channel_id, user_chat_id, start_time),
        uptime_loop(user_chat_id, start_time),
        heartbeat_loop(),                          # ← «пульс» раз на хвилину
    )

if __name__ == "__main__":
    asyncio.run(main())
