import asyncio
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError

from utils.filter import classify_message
from web import server

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

print(f"[ENV] .env at: {ENV_PATH}")
print(f"[ENV] API_ID={API_ID} (hash present: {'YES' if API_HASH else 'NO'})")

SESSION_FILE = (BASE_DIR / "telethon.session").as_posix()

client = TelegramClient(
    SESSION_FILE,
    API_ID,
    API_HASH,
    flood_sleep_threshold=120,
    device_model="Raspberry Pi 4",
    system_version="Debian 12 (Bookworm)",
    app_version="AirAlertBot 1.4",
    lang_code="uk",
    system_lang_code="uk",
    use_ipv6=False,
    connection_retries=None,
    retry_delay=3,
    request_retries=5,
)

message_queue = asyncio.Queue()
catch_up_messages = []
_official_entity = None
_last_official_message_id = 0

CHANNELS_PATH = BASE_DIR / "alert_sources" / "channels.json"
with open(CHANNELS_PATH, "r", encoding="utf-8") as f:
    monitored_channels = json.load(f)
print(f"[CFG] Loaded {len(monitored_channels)} channels from {CHANNELS_PATH}")

OFFICIAL_ALARM_SOURCES = {"air_alert_ua"}
SITUATION_SOURCES = {"war_monitor", "ukraine_pyxx", "cyyiiv_naorym"}

_RECENT_SIGS = set()
_MAX_SIGS = 500

_THROTTLE_SECONDS = 10.0
_last_handled_at: dict[str, float] = {}

ALARM_PHRASES = [
    "повітряна тривога", "відбій тривоги", "відбій повітряної тривоги",
    "воздушная тревога", "отбой тревоги",
]

THREAT_KEYWORDS = [
    "шахед", "шахеди", "shahed", "шahed", "мопед", "мопеди",
    "дрон", "дрони", "бпла", "безпілотник", "безпілотники",
    "ракета", "ракети", "ракетн",
    "іскандер", "кинджал", "калібр",
    "балістика", "балістичн",
    "пуск", "пуски", "запуск", "запуски",
    "зліт", "зльот", "взлёт", "взлет",
    "авіація", "авиация",
    "удар", "удари", "обстріл", "обстріли",
    "обстрел", "обстрелы",
    "вибух", "вибухи", "взрыв", "взрывы",
    "приліт", "прильот", "прильоти", "прилет", "прилеты",
    "сирена", "небезпека", "загроза", "опасность", "угроза",
    "🛵", "🚀", "💥", "✈️", "💣", "🛩️", "🎯", "🧨", "🚨", "🔥",
]

THREAT_KEYWORDS_RAPID = [
    "балістика", "балістичн", "баллистик",
    "міг-31", "миг-31", "міг31", "миг31", "міг", "миг",
    "кинджал", "искандер",
    "пуск", "пуски", "запуск", "запуски", "старт",
]

REGION_KEYWORDS = [
    "бровар", "бровари", "броварськ",
    "київська область", "київщина", "київ",
    "княжич", "требух", "калинівк", "велика димер", "мала димер",
    "богданівк", "красилівк", "погреб", "зазим", "літк", "пухівк",
    "рожн", "світильн", "семиполк", "квітнев", "перемог", "гогол", "калит",
    "бориспіл", "троєщин", "лісов", "дарниц", "вишгород", "обух",
    "ірпін", "буча", "гостомел", "вишнев", "васильк", "березан", "баришівк",
    "киев", "киевская область", "броварск", "бровары",
]

BRO_REVISOR_BONUS = {
    "на нас", "не летить", "летить", "не фіксується", "дорозвідка", "ппо",
}


def _contains_any(lower: str, keys: list[str] | set[str]) -> bool:
    return any(k in lower for k in keys)


def _is_situation_update(username: str, lower: str) -> bool:
    if username == "war_monitor":
        return (
            ("обстановка" in lower and "станом на" in lower)
            or "#обстановка" in lower
            or "стратегічна авіація" in lower and "флот" in lower
        )

    if username in {"ukraine_pyxx", "cyyiiv_naorym"}:
        return (
            "оцінка діяльності" in lower
            or "#зведення" in lower
            or "стратегічна авіація" in lower and "військово-транспортна авіація" in lower
            or "міг-31" in lower and "чорному морі" in lower
        )

    return False


def _passes_prefilter_when_active(lower: str, username: str) -> bool:
    if _contains_any(lower, ALARM_PHRASES):
        return True
    if _contains_any(lower, THREAT_KEYWORDS):
        return True
    if _contains_any(lower, REGION_KEYWORDS):
        return True
    if username == "bro_revisor" and _contains_any(lower, BRO_REVISOR_BONUS):
        return True
    return False


def _derive_flags(lower: str, username: str) -> tuple[bool, bool, bool]:
    region_hit = _contains_any(lower, REGION_KEYWORDS)
    rapid_hit = _contains_any(lower, THREAT_KEYWORDS_RAPID)
    revisor_bonus = False
    if username == "bro_revisor" and _contains_any(lower, BRO_REVISOR_BONUS):
        region_hit = True
        revisor_bonus = True
    return region_hit, rapid_hit, revisor_bonus


def _enrich_info_message(classified: dict, lower: str, username: str):
    region_hit, rapid_hit, revisor_bonus = _derive_flags(lower, username)
    classified["region_hit"] = region_hit
    classified["rapid_hit"] = rapid_hit
    if revisor_bonus:
        classified["revisor_bonus"] = True

    if not classified.get("threat_type"):
        if "ракета" in lower or "ракет" in lower:
            classified["threat_type"] = "ракета"
        elif "шахед" in lower or "дрон" in lower or "бпла" in lower:
            classified["threat_type"] = "шахед/дрон"
        elif _contains_any(lower, ["балістика", "баллистик", "миг", "міг", "кинджал", "искандер"]):
            classified["threat_type"] = "балістика/МіГ"


async def _queue_classified_message(classified: dict, text: str, username: str, url: str, msg_date):
    server.status["last_messages"].append({
        "text": text,
        "username": username,
        "url": url,
        "date": msg_date.isoformat(),
    })
    if len(server.status["last_messages"]) > 50:
        server.status["last_messages"] = server.status["last_messages"][-50:]

    classified["date"] = msg_date.replace(tzinfo=timezone.utc)
    await message_queue.put(classified)

    print(f"[TELEGRAM CHECKER] @{username} -> {classified}")
    await server.push_update()


@client.on(events.NewMessage(chats=monitored_channels))
async def handle_all_messages(event):
    username = getattr(event.chat, "username", None)
    if not username:
        return

    text = event.message.text or ""
    lower = text.lower()
    msg_id = event.message.id
    url = f"https://t.me/{username}/{msg_id}"

    is_situation = _is_situation_update(username, lower)

    # 1. Тротлінг та фільтрація тільки для звичайних інфо-повідомлень (зведення пропускаємо)
    if username not in OFFICIAL_ALARM_SOURCES:
        if not is_situation:
            if not _passes_prefilter_when_active(lower, username):
                return
            
            now = time.monotonic()
            last = _last_handled_at.get(username, 0.0)
            if (now - last) < _THROTTLE_SECONDS:
                return
            _last_handled_at[username] = now

    # 2. Хешування З ДОДАВАННЯМ ID повідомлення (вирішує проблему пропуску відбоїв)
    sig = hash((username, text, msg_id))
    if sig in _RECENT_SIGS:
        return
    _RECENT_SIGS.add(sig)
    if len(_RECENT_SIGS) > _MAX_SIGS:
        _RECENT_SIGS.pop()

    # 3. Класифікація з обходом для зведень
    classified = classify_message(text, url, source=username)
    
    if is_situation:
        if not classified:
            classified = {"source": username, "text": text, "url": url}
        classified["type"] = "situation"
        classified["situation_source"] = username
    else:
        if not classified:
            print(f"[TELEGRAM CHECKER] @{username} -> None (filtered by classifier)")
            return

    # 4. Коригування типів для неофіційних каналів
    if classified.get("type") in ("alarm", "all_clear") and username not in OFFICIAL_ALARM_SOURCES:
        classified["type"] = "info"

    if classified.get("type") == "info":
        _enrich_info_message(classified, lower, username)

    await _queue_classified_message(
        classified,
        text,
        username,
        url,
        event.message.date,
    )


async def official_alarm_poll_loop():
    global _official_entity, _last_official_message_id

    while True:
        try:
            if not client.is_connected():
                await asyncio.sleep(3)
                continue

            if _official_entity is None:
                _official_entity = await client.get_entity("air_alert_ua")

            latest = await client.get_messages(_official_entity, limit=1)
            if not latest:
                await asyncio.sleep(5)
                continue

            msg = latest[0]
            if not msg or not msg.id:
                await asyncio.sleep(5)
                continue

            if msg.id <= _last_official_message_id:
                await asyncio.sleep(5)
                continue

            _last_official_message_id = msg.id
            text = msg.text or ""
            url = f"https://t.me/air_alert_ua/{msg.id}"
            
            classified = classify_message(text, url, source="air_alert_ua")
            if classified:
                # ТУТ ТАКОЖ ДОДАНО msg.id ДЛЯ СИНХРОННОСТІ З ОСНОВНИМ ЦИКЛОМ
                sig = hash(("air_alert_ua", text, msg.id)) 
                if sig not in _RECENT_SIGS:
                    _RECENT_SIGS.add(sig)
                    if len(_RECENT_SIGS) > _MAX_SIGS:
                        _RECENT_SIGS.pop()
                    print(f"[OFFICIAL POLL] picked up message {msg.id}")
                    await _queue_classified_message(
                        classified,
                        text,
                        "air_alert_ua",
                        url,
                        msg.date,
                    )
        except FloodWaitError as e:
            print(f"[OFFICIAL POLL] FloodWait {e.seconds}s")
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            print(f"[OFFICIAL POLL] error: {e}")

        await asyncio.sleep(5)


async def start_monitoring():
    # Запуск фонового пулера офіційних тривог
    asyncio.create_task(official_alarm_poll_loop())
    await client.run_until_disconnected()


async def check_telegram_channels():
    if not message_queue.empty():
        return await message_queue.get()
    return None


async def fetch_last_messages(minutes: int):
    if not await client.is_user_authorized():
        print("Not authorized to fetch historical messages.")
        return

    monitor_start_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    print(f"Loading historical messages from {monitor_start_time.isoformat()}")

    for username in monitored_channels:
        try:
            entity = await client.get_entity(username)
            try:
                messages = await client.get_messages(entity, limit=50)
            except FloodWaitError as e:
                print(f"Flood wait {e.seconds}s on {username}")
                await asyncio.sleep(e.seconds)
                continue

            for msg in reversed(messages):
                if msg.date.replace(tzinfo=timezone.utc) < monitor_start_time:
                    continue

                lower = (msg.text or "").lower()
                url = f"https://t.me/{username}/{msg.id}"
                cl = classify_message(msg.text or "", url, source=username)
                
                is_situation = _is_situation_update(username, lower)
                
                # Обхід класифікатора для зведень в історії
                if is_situation:
                    if not cl:
                        cl = {"source": username, "text": msg.text or "", "url": url}
                    cl["type"] = "situation"
                    cl["situation_source"] = username
                else:
                    if not cl:
                        continue

                if cl.get("type") in ("alarm", "all_clear") and username not in OFFICIAL_ALARM_SOURCES:
                    cl["type"] = "info"

                if cl.get("type") == "info":
                    _enrich_info_message(cl, lower, username)

                cl["date"] = msg.date.replace(tzinfo=timezone.utc)
                catch_up_messages.append(cl)

            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"Failed to fetch messages from {username}: {e}")


async def get_catch_up_messages():
    return catch_up_messages