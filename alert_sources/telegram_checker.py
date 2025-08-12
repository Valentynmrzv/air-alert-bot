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

# =========================
# Канали з абсолютного шляху
# =========================
CHANNELS_PATH = BASE_DIR / "alert_sources" / "channels.json"
with open(CHANNELS_PATH, "r", encoding="utf-8") as f:
    monitored_channels = json.load(f)
print(f"[CFG] Loaded {len(monitored_channels)} channels from {CHANNELS_PATH}")

# 🔒 «тривога/відбій» довіряємо тільки офіційному
OFFICIAL_ALARM_SOURCES = {"air_alert_ua"}

# Антиспам
_RECENT_SIGS = set()
_MAX_SIGS = 500
# ⏱️ Тротлінг неофіційних каналів під час активної тривоги
_THROTTLE_SECONDS = 10.0
_last_handled_at: dict[str, float] = {}

# =========================
# Ключі для префільтра під час активної тривоги
# =========================
ALARM_PHRASES = [
    "повітряна тривога", "відбій тривоги",
    "воздушная тревога", "отбой тревоги",
]

# 1) Загрози (емодзі + слова/стеми; перевіряємо як підрядки у lower)
THREAT_KEYWORDS = [
    # емодзі
    "🛵", "🚀", "💥", "✈️", "💣", "🛩️", "🎯", "🧨", "🚨", "🔥",
    # БПЛА / «мопеди»
    "шахед", "шахеди", "shahed", "шаhed", "герaнь", "герань", "герaнь-2", "герань-2",
    "дрон", "дрони", "бпла", "безпілотник", "безпілотники",
    "мопед", "мопеди", "мавік", "mavic", "ланцет", "lancet",
    # ракети / типи
    "ракета", "ракети", "ракетн", "крила", "крилат", "крылат",  # крилата ракета
    "іскандер", "искандер", "кинжал", "калібр", "калибр",
    "х-101", "х101", "x-101", "x101", "ха-101", "ха101",
    "х-22", "х22", "x-22", "x22",
    "х-47", "х47", "x-47", "x47",
    # інші тригери
    "пуск", "пуски", "запуск", "запуски",
    "зліт", "зльот", "взлет", "авіація", "авиация",
    "удар", "удари", "обстріл", "обстріли", "обстрел", "обстрелы",
    "вибух", "вибухи", "взрыв", "взрывы",
    "приліт", "прильот", "прильоти", "прилет", "прилеты",
    "сирена", "небезпека", "загроза", "опасност", "угроза",
]

# 2) Регіон (Київ/Київщина + Броварський район + довколишні населені пункти) — стеми
REGION_KEYWORDS = [
    # Київ/Київщина
    "київ", "київщина", "київська область", "столиця",
    "киев", "киевская область", "столица",
    # Бровари/район
    "бровар", "бровари", "броварськ", "броварский", "броварского",
    # населені пункти та мікрорайони (UA/RU; з урахуванням стемів/варіацій)
    "княжич", "требух", "калинівк",
    "велика димер", "в. димер", "мала димер", "м. димер",
    "богданівк", "богдановк", "красилівк", "красиловк",
    "погреби", "зазим", "літки", "литки", "пухівк", "пуховк",
    "рожн", "світильн", "светильн", "семиполк",
    "квітнев", "квитнев", "перемог", "гогол", "калита",
    # довкола Києва
    "бориспіл", "борисполь", "троєщин", "троещин",
    "лісов", "лісовий масив", "лесной", "лесной массив",
    "дарниц", "вишгород", "вышгород",
    "обух", "ірпін", "ирпень",
    "буча", "гостомел", "гостоміль",
    "вишнев", "васильк", "березан", "баришівк", "барышевк",
]

# 3) Додаткові тригери для bro_revisor під час активної тривоги
BRO_REVISOR_BONUS = {"на нас", "не летить", "летить"}

def _passes_prefilter_when_active(lower: str, username: str | None) -> bool:
    """Під час активної тривоги пропускаємо, якщо:
       - є офіційні фрази (ALARM_PHRASES), або
       - є ХОЧ ОДНА загроза (THREAT_KEYWORDS), або
       - є ХОЧ ОДИН топонім (REGION_KEYWORDS), або
       - для bro_revisor є фрази з BRO_REVISOR_BONUS.
    """
    if any(p in lower for p in ALARM_PHRASES):
        return True
    if any(k in lower for k in THREAT_KEYWORDS):
        return True
    if any(k in lower for k in REGION_KEYWORDS):
        return True
    if username == "bro_revisor" and any(k in lower for k in BRO_REVISOR_BONUS):
        return True
    return False

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

        if not _passes_prefilter_when_active(lower, username):
            return

    # Debounce (антидубль)
    sig = hash((username, text))
    if sig in _RECENT_SIGS:
        return
    _RECENT_SIGS.add(sig)
    if len(_RECENT_SIGS) > _MAX_SIGS:
        _RECENT_SIGS.pop()

    # Класифікація (передаємо джерело у фільтр)
    classified = classify_message(text, url, source=username)
    print(f"[TELEGRAM CHECKER] @{username} → {classified}")

    if not classified:
        return

    # Безпека: будь-які alarm/all_clear не з офіційного знижуємо до info
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

# catch-up не викликаємо з main.py (економія лімітів)
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
