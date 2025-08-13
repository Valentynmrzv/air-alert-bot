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
BASE_DIR = Path(__file__).resolve().parents[1]  # .../air-alert-bot
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
STRING = (os.getenv("TELETHON_SESSION") or "").strip()

print(f"[ENV] .env at: {ENV_PATH}")
print(f"[ENV] TELETHON_SESSION loaded: {'YES' if STRING else 'NO'}")
print(f"[ENV] API_ID={API_ID} (hash present: {'YES' if API_HASH else 'NO'})")

# Telethon client (StringSession якщо задано, інакше файлова "session")
client = TelegramClient(
    StringSession(STRING) if STRING else "session",
    API_ID,
    API_HASH,
    flood_sleep_threshold=120
)

# Черга для main.py
message_queue = asyncio.Queue()
catch_up_messages: list[dict] = []

# Канали з файлу (абсолютний шлях)
CHANNELS_PATH = BASE_DIR / "alert_sources" / "channels.json"
with open(CHANNELS_PATH, "r", encoding="utf-8") as f:
    monitored_channels = json.load(f)
print(f"[CFG] Loaded {len(monitored_channels)} channels from {CHANNELS_PATH}")

# Офіційне джерело тривоги/відбою
OFFICIAL_ALARM_SOURCES = {"air_alert_ua"}

# Debounce на однакові повідомлення
_RECENT_SIGS = set()
_MAX_SIGS = 600

# Тротлінг для неофіційних
_THROTTLE_SECONDS = 10.0
_last_handled_at: dict[str, float] = {}  # username -> monotonic ts

# Ключі для префільтра під час активної тривоги
ALARM_PHRASES = [
    "повітряна тривога", "відбій тривоги",
    "воздушная тревога", "отбой тревоги",
]

THREAT_KEYWORDS = [
    # емодзі та маркери
    "🛵", "🚀", "💥", "✈️", "💣", "🛩️", "🎯", "🧨", "🚨", "🔥",
    # укр/рос/лат
    "шахед", "shahed", "мопед",
    "дрон", "дрони", "бпла", "безпілот",
    "ракета", "ракетн",
    "баліст", "баллист",
    "іскандер", "кинжал", "калібр",
    "пуск", "пуски", "запуск",
    "зліт", "злет", "міг", "mig", "міг-31", "міг-31к", "mig-31", "mig-31k",
    "ту-22", "tu-22",
    "удар", "обстріл", "обстрел",
    "вибух", "взрыв", "приліт", "прилет",
    "сирена", "небезпека", "угроза",
]

REGION_KEYWORDS = [
    # Бровари/район та Київщина
    "бровар", "бровари", "броварськ",
    "київська область", "київщина", "київ",
    # околиці (стемінг)
    "княжич", "требух", "калинівк", "велика димер", "мала димер",
    "богданівк", "красилівк", "погреб", "зазим", "літк", "пухівк",
    "рожн", "світильн", "семиполк", "квітнев", "перемог", "гогол", "калит",
    # ближні локації
    "бориспіл", "троєщин", "лісов", "дарниц", "вишгород", "обух",
    "ірпін", "буча", "гостомел", "вишнев", "васильк", "березан", "баришівк",
]

# Додаткові фрази для @bro_revisor — пропускати короткі апдейти
BRO_REVISOR_BONUS = [
    "на нас", "не летить", "летить", "не фіксується", "дорозвідка",
    "під обстрілом", "обстріл", "обстріли",
    "прильот", "прильоти", "приліт",
    "вибух", "вибухи",
    "ракета", "ракети",
    "дрон", "дрони", "бпла",
    "загроза", "небезпека",
]

def _passes_prefilter_when_active(lower: str, username: str) -> bool:
    """
    Під час активної тривоги пропускаємо, якщо:
      - є фрази «тривога/відбій», або
      - є ХОЧ ОДНА загроза, або
      - є ХОЧ ОДНА локація, або
      - це bro_revisor з його бонус-словами.
    """
    if any(p in lower for p in ALARM_PHRASES):
        return True
    if any(k in lower for k in THREAT_KEYWORDS):
        return True
    if any(k in lower for k in REGION_KEYWORDS):
        return True
    if username and username.lower() == "bro_revisor":
        if any(k in lower for k in BRO_REVISOR_BONUS):
            return True
    return False


@client.on(events.NewMessage(chats=monitored_channels))
async def handle_all_messages(event):
    username = getattr(event.chat, "username", None)
    if not username:
        return

    text = event.message.text or ""
    lower = text.lower()
    url = f"https://t.me/{username}/{event.message.id}"

    alert_active = bool(server.status.get("alert_active"))

    # Неофіційні читаємо лише під час активної тривоги
    if username not in OFFICIAL_ALARM_SOURCES and not alert_active:
        return

    # Тротлінг + префільтр для неофіційних під час активної тривоги
    if username not in OFFICIAL_ALARM_SOURCES:
        now = time.monotonic()
        last = _last_handled_at.get(username, 0.0)
        if (now - last) < _THROTTLE_SECONDS:
            return
        _last_handled_at[username] = now

        if not _passes_prefilter_when_active(lower, username):
            return

    # Debounce на дублікати
    sig = hash((username, text))
    if sig in _RECENT_SIGS:
        return
    _RECENT_SIGS.add(sig)
    if len(_RECENT_SIGS) > _MAX_SIGS:
        _RECENT_SIGS.pop()

    # Класифікація (ВАЖЛИВО: передати source=username)
    classified = classify_message(text, url, source=username)
    print(f"[TELEGRAM CHECKER] @{username} → {classified}")

    if not classified:
        return

    # Безпека: алерт/відбій тільки з офіційного
    if classified["type"] in ("alarm", "all_clear") and username not in OFFICIAL_ALARM_SOURCES:
        classified["type"] = "info"

    # Оновлюємо веб-статус (короткий буфер)
    server.status["last_messages"].append({
        "text": text,
        "username": username,
        "url": url,
        "date": event.message.date.isoformat(),
    })
    if len(server.status["last_messages"]) > 50:
        server.status["last_messages"] = server.status["last_messages"][-50:]

    # Кладемо у чергу для main.py
    classified["date"] = event.message.date.replace(tzinfo=timezone.utc)
    await message_queue.put(classified)

    # Live-оновлення веб-UI
    await server.push_update()


async def start_monitoring():
    await client.start()
    await client.run_until_disconnected()


async def check_telegram_channels():
    if not message_queue.empty():
        return await message_queue.get()
    return None


# catch-up НЕ ВИКЛИКАТИ з main.py (щоб не плодити API-запити)
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
