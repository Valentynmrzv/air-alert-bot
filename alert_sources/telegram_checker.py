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
BASE_DIR = Path(__file__).resolve().parents[1]  # корінь проекту
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
STRING = (os.getenv("TELETHON_SESSION") or "").strip()

print(f"[ENV] .env at: {ENV_PATH}")
print(f"[ENV] TELETHON_SESSION loaded: {'YES' if STRING else 'NO'}")
print(f"[ENV] API_ID={API_ID} (hash present: {'YES' if API_HASH else 'NO'})")

# ✅ клієнт Telethon зі StringSession (fallback на файл "session", якщо STRING не заданий)
client = TelegramClient(
    StringSession(STRING) if STRING else "session",
    API_ID,
    API_HASH,
    flood_sleep_threshold=120
)

message_queue = asyncio.Queue()
catch_up_messages = []

# =========================
# Канали — шлях по абсолютному шляху
# =========================
CHANNELS_PATH = BASE_DIR / "alert_sources" / "channels.json"
with open(CHANNELS_PATH, "r", encoding="utf-8") as f:
    monitored_channels = json.load(f)
print(f"[CFG] Loaded {len(monitored_channels)} channels from {CHANNELS_PATH}")

# 🔒 «тривога/відбій» довіряємо тільки офіційному
OFFICIAL_ALARM_SOURCES = {"air_alert_ua"}

# Debounce на однакові тексти/репости (глобально)
_RECENT_SIGS = set()
_MAX_SIGS = 500

# ⏱️ Тротлінг по каналах (окрім офіційних): не частіше ніж раз на 10 секунд
_THROTTLE_SECONDS = 10.0
_last_handled_at: dict[str, float] = {}  # username -> monotonic ts

# =========================
# Ключі та фрази
# =========================
ALARM_PHRASES = [
    "повітряна тривога", "відбій тривоги",
    "воздушная тревога", "отбой тревоги",
]

# Загрози — ширший пул для базового префільтра
THREAT_KEYWORDS = [
    "шахед", "шахеди", "shahed", "шаhed", "мопед", "мопеди",
    "дрон", "дрони", "бпла", "безпілотник", "безпілотники",
    "ракета", "ракети", "ракетн",
    "іскандер", "кинжал", "калібр",
    "балістика", "балістичн",
    "пуск", "пуски", "запуск", "запуски",
    "зліт", "зльот", "взлёт", "взлет",
    "авіація", "авиация",
    "удар", "удари", "обстріл", "обстріли",
    "обстрел", "обстрелы",
    "вибух", "вибухи", "взрыв", "взрывы",
    "приліт", "прильот", "прильоти", "прилет", "прилеты",
    "сирена", "небезпека", "загроза", "опасност", "угроза",
    # емодзі (можуть траплятися)
    "🛵", "🚀", "💥", "✈️", "💣", "🛩️", "🎯", "🧨", "🚨", "🔥",
]

# Швидка загроза — дозволяє проходити без GEO під час тривоги
THREAT_KEYWORDS_RAPID = [
    # балістика / МіГ / пуски
    "балістика", "балістичн", "баллистик",
    "миг-31", "міг-31", "миг-31", "міг-31", "міг31", "миг31", "міг", "миг",
    "кинжал", "искандер",
    "пуск", "пуски", "запуск", "запуски", "старт",
]

# GEO ключі (стеми і близькі локації)
REGION_KEYWORDS = [
    # Бровари/район (включаючи 'бровари', 'броварськ' тощо)
    "бровар", "бровари", "броварськ",
    # Область / Київ / Київщина
    "київська область", "київщина", "київ",
    # Околиці (стемінг)
    "княжич", "требух", "калинівк", "велика димер", "мала димер",
    "богданівк", "красилівк", "погреб", "зазим", "літк", "пухівк",
    "рожн", "світильн", "семиполк", "квітнев", "перемог", "гогол", "калит",
    # Ближні локації
    "бориспіл", "троєщин", "лісов", "дарниц", "вишгород", "обух",
    "ірпін", "буча", "гостомел", "вишнев", "васильк", "березан", "баришівк",
    # RU-варианти базових назв (мінімально)
    "киев", "киевская область", "броварск", "бровары",
]

# Бонус-фрази для bro_revisor — навіть без GEO
BRO_REVISOR_BONUS = {
    "на нас", "не летить", "летить", "не фіксується", "дорозвідка"
}

def _contains_any(lower: str, keys: list[str] | set[str]) -> bool:
    return any(k in lower for k in keys)

def _passes_prefilter_when_active(lower: str, username: str) -> bool:
    """Під час активної тривоги пропускаємо якщо:
       - є офіційні фрази (ALARM_PHRASES), або
       - є ХОЧ ОДНА загроза (THREAT_KEYWORDS), або
       - є ХОЧ ОДНА локація (REGION_KEYWORDS),
       - або це bro_revisor з бонус-фразою.
    """
    if _contains_any(lower, ALARM_PHRASES):
        return True
    if _contains_any(lower, THREAT_KEYWORDS):
        return True
    if _contains_any(lower, REGION_KEYWORDS):
        return True
    if username == "bro_revisor" and _contains_any(lower, BRO_REVISOR_BONUS):
        return True
    return False

def _derive_flags(lower: str, username: str) -> tuple[bool, bool]:
    """Повертає (region_hit, rapid_hit) для INFO."""
    region_hit = _contains_any(lower, REGION_KEYWORDS)
    rapid_hit = _contains_any(lower, THREAT_KEYWORDS_RAPID)

    # Бонуси для bro_revisor: короткі фрази типу «на нас», «летить» і т.д.
    if username == "bro_revisor" and _contains_any(lower, BRO_REVISOR_BONUS):
        region_hit = True  # поводимось як з локальною гео-важливістю

    return region_hit, rapid_hit

@client.on(events.NewMessage(chats=monitored_channels))
async def handle_all_messages(event):
    username = getattr(event.chat, 'username', None)
    if not username:
        return

    text = event.message.text or ""
    lower = text.lower()
    url = f"https://t.me/{username}/{event.message.id}"

    alert_active = bool(server.status.get("alert_active"))

    # Неофіційні канали: до тривоги — не читаємо взагалі
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

    # Debounce на однакові тексти/репости
    sig = hash((username, text))
    if sig in _RECENT_SIGS:
        return
    _RECENT_SIGS.add(sig)
    if len(_RECENT_SIGS) > _MAX_SIGS:
        _RECENT_SIGS.pop()

    # Класифікація (додаємо source для прозорості)
    classified = classify_message(text, url, source=username)
    # Якщо класифікатор нічого не повернув — вихід
    if not classified:
        print(f"[TELEGRAM CHECKER] @{username} → None")
        return

    # Безпека: будь-які alarm/all_clear не з офіційного знизити до info
    if classified["type"] in ("alarm", "all_clear") and username not in OFFICIAL_ALARM_SOURCES:
        classified["type"] = "info"

    # Доповнюємо INFO прапорцями region_hit / rapid_hit
    if classified["type"] == "info":
        region_hit, rapid_hit = _derive_flags(lower, username)
        classified["region_hit"] = region_hit
        classified["rapid_hit"]  = rapid_hit

        # Якщо класифікатор не визначив threat_type, спробуємо грубо
        if not classified.get("threat_type"):
            if "ракета" in lower or "ракет" in lower:
                classified["threat_type"] = "ракета"
            elif "шахед" in lower or "дрон" in lower or "бпла" in lower:
                classified["threat_type"] = "шахед/дрон"
            elif _contains_any(lower, ["балістика", "баллистик", "миг", "міг", "кинжал", "искандер"]):
                classified["threat_type"] = "балістика/МіГ"

    # оновлюємо веб-статус (короткий буфер)
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

    print(f"[TELEGRAM CHECKER] @{username} → {classified}")
    # Live-оновлення
    await server.push_update()

async def start_monitoring():
    await client.start()
    await client.run_until_disconnected()

async def check_telegram_channels():
    if not message_queue.empty():
        return await message_queue.get()
    return None

# ⚠️ catch-up краще НЕ ВИКЛИКАТИ з main.py (зайві API-запити)
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

                        # Додамо прапорці і тут, щоб catch-up теж мав логіку
                        lower = (msg.text or "").lower()
                        if cl["type"] == "info":
                            region_hit, rapid_hit = _derive_flags(lower, username)
                            cl["region_hit"] = region_hit
                            cl["rapid_hit"] = rapid_hit

                        cl["date"] = msg.date.replace(tzinfo=timezone.utc)
                        catch_up_messages.append(cl)
            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"❌ Помилка підвантаження повідомлень з {username}: {e}")

async def get_catch_up_messages():
    return catch_up_messages
