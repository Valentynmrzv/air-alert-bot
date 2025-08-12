# alert_sources/telegram_checker.py
import os
import asyncio
import time
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession
from dotenv import load_dotenv

from utils.filter import classify_message
from web import server  # live-статус та SSE

# =========================
# Завантаження .env по абсолютному шляху
# =========================
BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
STRING = (os.getenv("TELETHON_SESSION") or "").strip()

print(f"[ENV] .env at: {ENV_PATH}")
print(f"[ENV] TELETHON_SESSION loaded: {'YES' if STRING else 'NO'}")
print(f"[ENV] API_ID={API_ID} (hash present: {'YES' if API_HASH else 'NO'})")

client = TelegramClient(
    StringSession(STRING) if STRING else "session",
    API_ID,
    API_HASH,
    flood_sleep_threshold=120
)

message_queue = asyncio.Queue()
catch_up_messages = []

CHANNELS_PATH = BASE_DIR / "alert_sources" / "channels.json"
with open(CHANNELS_PATH, "r", encoding="utf-8") as f:
    monitored_channels = json.load(f)
print(f"[CFG] Loaded {len(monitored_channels)} channels from {CHANNELS_PATH}")

OFFICIAL_ALARM_SOURCES = {"air_alert_ua"}

_RECENT_SIGS = set()
_MAX_SIGS = 500
_THROTTLE_SECONDS = 10.0
_last_handled_at: dict[str, float] = {}

ALARM_PHRASES = [
    "повітряна тривога", "відбій тривоги",
    "воздушная тревога", "отбой тревоги",
]

THREAT_KEYWORDS = [
    "шахед", "shahed", "бпла", "дрон", "дрони",
    "ракета", "ракетн", "баліст", "іскандер", "кинжал", "калібр",
    "пуск", "запуск", "зліт", "зльот", "авіація",
    "удар", "обстріл", "вибух", "приліт", "прильот",
    "сирена", "небезпека", "загроза", "🛵", "🚀", "💥", "✈️", "💣",
]

REGION_KEYWORDS = [
    "бровар", "бровари", "броварський",
    "київська область", "київщина", "київ",
    "княжич", "требух", "калинівк", "велика димер", "мала димер",
    "богданівк", "красилівк", "погреби", "зазим", "літки", "пухівк",
    "рожни", "світильн", "семиполк", "квітнев", "перемог", "гогол", "калита",
    "бориспіл", "троєщин", "лісов", "дарниц", "вишгород", "обух", "ірпін", "буча",
    "гостомел", "вишнев", "васильк", "березан", "баришівк",
]

def _passes_prefilter_when_active(lower: str) -> bool:
    # під час активної тривоги пропускаємо, якщо є фрази тривоги/відбою, або є загроза, або є топонім
    return any(p in lower for p in ALARM_PHRASES) or \
           any(k in lower for k in THREAT_KEYWORDS) or \
           any(k in lower for k in REGION_KEYWORDS)

@client.on(events.NewMessage(chats=monitored_channels))
async def handle_all_messages(event):
    username = getattr(event.chat, 'username', None)
    if not username:
        return

    text = event.message.text or ""
    lower = text.lower()
    url = f"https://t.me/{username}/{event.message.id}"

    alert_active = bool(server.status.get("alert_active"))

    # Неофіційні канали: читаємо тільки під час активної тривоги
    if username not in OFFICIAL_ALARM_SOURCES and not alert_active:
        return

    # Тротлінг/префільтр для неофіційних під час активної тривоги
    if username not in OFFICIAL_ALARM_SOURCES:
        now = time.monotonic()
        last = _last_handled_at.get(username, 0.0)
        if (now - last) < _THROTTLE_SECONDS:
            return
        _last_handled_at[username] = now
        if not _passes_prefilter_when_active(lower):
            return

    # Debounce
    sig = hash((username, text))
    if sig in _RECENT_SIGS:
        return
    _RECENT_SIGS.add(sig)
    if len(_RECENT_SIGS) > _MAX_SIGS:
        _RECENT_SIGS.pop()

    # Класифікація (передаємо джерело)
    classified = classify_message(text, url, source=username)
    print(f"[TELEGRAM CHECKER] @{username} → {classified}")

    if not classified:
        return

    # Безпека: будь-які alarm/all_clear не з офіційного знизити до info
    if classified["type"] in ("alarm", "all_clear") and username not in OFFICIAL_ALARM_SOURCES:
        classified["type"] = "info"

    # оновлюємо веб-статус
    server.status["last_messages"].append({
        "text": text,
        "username": username,
        "url": url,
        "date": event.message.date.isoformat(),
    })
    if len(server.status["last_messages"]) > 50:
        server.status["last_messages"] = server.status["last_messages"][-50:]

    # у чергу для основного циклу
    classified["date"] = event.message.date.replace(tzinfo=timezone.utc)
    await message_queue.put(classified)
    await server.push_update()

async def start_monitoring():
    await client.start()
    await client.run_until_disconnected()

async def check_telegram_channels():
    if not message_queue.empty():
        return await message_queue.get()
    return None

# catch-up не викликаємо з main.py
async def fetch_last_messages(minutes: int):
    if not await client.is_user_authorized():
        print("❗ Не авторизовано для підвантаження повідомлень.")
        return

    monitor_start_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    print(f"🔄 Підвантаження повідомлень з {monitor_start_time.isoformat()}")

    for username in monitored_channels:
        try:
            entity = await client.get_entity(username)
            try:
                messages = await client.get_messages(entity, limit=50)
            except FloodWaitError as e:
                print(f"⏳ Flood wait {e.seconds}s на {username}")
                await asyncio.sleep(e.seconds)
                continue

            for msg in reversed(messages):
                if msg.date.replace(tzinfo=timezone.utc) >= monitor_start_time:
                    cl = classify_message(msg.text or "", f"https://t.me/{username}/{msg.id}", source=username)
                    if cl:
                        if cl["type"] in ("alarm", "all_clear") and username not in OFFICIAL_ALARM_SOURCES:
                            cl["type"] = "info"
                        cl["date"] = msg.date.replace(tzinfo=timezone.utc)
                        catch_up_messages.append(cl)
            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"❌ Помилка підвантаження повідомлень з {username}: {e}")

async def get_catch_up_messages():
    return catch_up_messages


# THREAT_KEYWORDS = [
#     "🛵", "🚀", "💥", "✈️", "💣",
#     "шахед", "шахеди", "shahed", "шаhed",
#     "дрон", "дрони", "бпла", "безпілотник", "безпілотники",
#     "ракета", "ракети", "ракетн",
#     "балістика", "балістичн",
#     "іскандер", "кинжал", "калібр",
#     "пуск", "пуски", "запуск", "запуски",
#     "зліт", "зльот", "авіація",
#     "удар", "удари", "обстріл", "обстріли",
#     "вибух", "вибухи", "приліт", "прильот", "прильоти",
#     "сирена", "небезпека", "загроза",
#     "шахедов", "дронов", "беспилотник", "беспилотники",
#     "ракеты", "ракетн", "баллистик", "искандер", "калибр",
#     "взлет", "авиация",
#     "удар", "удары", "обстрел", "обстрелы",
#     "взрыв", "взрывы", "прилет", "прилеты",
#     "опасност", "угроза",
# ]

# REGION_KEYWORDS = [
#     "бровар", "бровари", "броварський",
#     "київська область", "київщина", "київ",  # тільки як хінт для info
#     "княжич", "требух", "калинівк", "велика димер", "мала димер",
#     "богданівк", "красилівк", "погреби", "зазим", "літки", "пухівк",
#     "рожни", "світильн", "семиполк", "квітнев", "перемог", "гогол", "калита",
#     "бориспіл", "троєщин", "лісов", "дарниц", "вишгород", "обух", "ірпін", "буча",
#     "гостомел", "вишнев", "васильк", "березан", "баришівк",
# ]