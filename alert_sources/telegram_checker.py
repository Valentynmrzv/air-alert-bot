# alert_sources/telegram_checker.py
import os
import asyncio
import time
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from dotenv import load_dotenv
from utils.filter import classify_message
import json
from web import server  # для live-статусу та SSE

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# ✅ авто-сон на FloodWait, щоб акаунт не «викидало»
client = TelegramClient(
    "session",
    API_ID,
    API_HASH,
    flood_sleep_threshold=120
)

message_queue = asyncio.Queue()
catch_up_messages = []

with open("alert_sources/channels.json", "r", encoding="utf-8") as f:
    monitored_channels = json.load(f)

# 🔒 «тривога/відбій» довіряємо тільки офіційному
OFFICIAL_ALARM_SOURCES = {"air_alert_ua"}

# Debounce на однакові тексти/репости (глобально)
_RECENT_SIGS = set()
_MAX_SIGS = 500

# ⏱️ Тротлінг по каналах (окрім офіційних): не частіше ніж раз на 10 секунд
_THROTTLE_SECONDS = 10.0
_last_handled_at: dict[str, float] = {}  # username -> monotonic ts

# =========================
# РОЗШИРЕНІ КЛЮЧІ ДЛЯ ПРЕФІЛЬТРА
# =========================

# 1) Загрози (UA + RU + варіанти відмінків/множини; перевіряємо як підрядок у lower)
THREAT_KEYWORDS = [
    # базові
    "шахед", "шахеди", "шаhed",  # інколи «shahed» латиницею
    "дрон", "дрони", "бпла", "безпілотник", "безпілотники",
    "ракета", "ракети", "ракетний",
    "балістика", "балістичн",  # покриває балістична/і/і т.д.
    "іскандер", "кинжал", "калібр",
    "пуск", "пуски", "запуск", "запуски",
    "зліт", "зльот", "авіація",
    "удар", "удари", "обстріл", "обстріли",
    "вибух", "вибухи", "приліт", "прильот", "прильоти",
    "сирена", "небезпека", "загроза",

    # RU-варіанти
    "шахедов", "дронов", "беспилотник", "беспилотники",
    "ракета", "ракеты", "баллистик", "искандер", "кинжал", "калибр",
    "пуск", "пуски", "запуск", "запуски",
    "взлет", "авиация",
    "удар", "удары", "обстрел", "обстрелы",
    "взрыв", "взрывы", "прилет", "прилеты",
    "сирена", "опасност", "угроза",
]

# 2) Регіон (Київ/Київщина + Броварський район + довколишні населені пункти)
REGION_KEYWORDS = [
    # Київщина загалом
    "київ", "київщина", "київська область", "столиця",
    "киев", "киевская область", "столица",

    # Бровари/район
    "бровар", "бровари", "броварський", "броварского", "броварский",

    # Населені пункти Броварського району (та близькі до броварів)
    "княжичі", "княжичи",
    "требухів", "требухов",
    "калинівка", "калиновка",
    "велика димерка", "великa димерка", "в. димерка", "велика димерк",
    "мала димерка", "м. димерка", "мала димерк",
    "богданівка", "богдановка",
    "красилівка", "красиловка",
    "погреби",
    "зазим'я", "зазимье", "зазимя",
    "літки", "литки",
    "рожни",
    "світильня", "светильня",
    "семиполки",
    "квітневе", "квитневое",
    "перемога", "перемога (бр)",  # інколи додають уточнення
    "гоголів", "гоголев",
    "кали́та", "калита",

    # Інші «сусідні»/часто згадувані точки довкола Києва
    "бориспіль", "борисполь",
    "троєщина", "троещина",
    "лісовий", "лісовий масив", "лесной", "лесной массив",
    "дарниця", "дарница",
    "вишгород", "вышгород",
    "обухів", "обухов",
    "ірпінь", "ірпін", "ирпень",
    "буча",
    "гостомель", "гостоміль",
    "вишневе", "вишневое",
    "васильків", "васильков",
    "березань", "баришівка", "барышевка",
]

# контекстні фрази про офіційний стан тривоги
ALARM_PHRASES = ["повітряна тривога", "відбій тривоги", "воздушная тревога", "отбой тревоги"]


def _passes_prefilter(lower: str) -> bool:
    """Пропускаємо, якщо:
       - є фрази про офіційний стан (ALARM_PHRASES), або
       - (є хоч одна загроза з THREAT_KEYWORDS) І (є хоч один топонім з REGION_KEYWORDS).
    """
    if any(p in lower for p in ALARM_PHRASES):
        return True
    has_threat = any(k in lower for k in THREAT_KEYWORDS)
    has_region = any(k in lower for k in REGION_KEYWORDS)
    return has_threat and has_region


@client.on(events.NewMessage(chats=monitored_channels))
async def handle_all_messages(event):
    username = getattr(event.chat, 'username', None)
    if not username:
        return

    text = event.message.text or ""
    lower = text.lower()
    url = f"https://t.me/{username}/{event.message.id}"

    # ⏱️ Пер-канальний тротлінг (крім офіційних)
    if username not in OFFICIAL_ALARM_SOURCES:
        now = time.monotonic()
        last = _last_handled_at.get(username, 0.0)
        if (now - last) < _THROTTLE_SECONDS:
            return
        _last_handled_at[username] = now

    # 🔕 РОЗШИРЕНИЙ ГРУБИЙ PREFILTER
    if not _passes_prefilter(lower):
        return

    # Debounce на однакові тексти/репости
    sig = hash((username, text))
    if sig in _RECENT_SIGS:
        return
    _RECENT_SIGS.add(sig)
    if len(_RECENT_SIGS) > _MAX_SIGS:
        # видаляємо довільний елемент, щоб не рости безмежно
        _RECENT_SIGS.pop()

    # 1) Спочатку класифікація (лог — тільки для релевантного)
    classified = classify_message(text, url)
    # Для прозорості в логах:
    print(f"[TELEGRAM CHECKER] @{username} → {classified}")

    if not classified:
        return

    # 🔒 «тривога/відбій» приймаємо лише від офіційного
    if classified["type"] in ("alarm", "all_clear") and username not in OFFICIAL_ALARM_SOURCES:
        classified["type"] = "info"

    # 2) Оновлюємо веб-статус (короткий буфер)
    server.status["last_messages"].append({
        "text": text,
        "username": username,
        "url": url,
        "date": event.message.date.isoformat(),
    })
    if len(server.status["last_messages"]) > 50:
        server.status["last_messages"] = server.status["last_messages"][-50:]

    # 3) Кладемо у чергу для основного циклу
    classified["date"] = event.message.date.replace(tzinfo=timezone.utc)
    await message_queue.put(classified)

    # Live-оновлення у веб
    await server.push_update()


async def start_monitoring():
    await client.start()
    await client.run_until_disconnected()


async def check_telegram_channels():
    if not message_queue.empty():
        return await message_queue.get()
    return None


# ⚠️ catch-up залишено, але краще НЕ ВИКЛИКАТИ його з main.py, щоб не плодити API-запити
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
                    classified = classify_message(msg.text or "", f"https://t.me/{username}/{msg.id}")
                    if classified:
                        if classified["type"] in ("alarm", "all_clear") and username not in OFFICIAL_ALARM_SOURCES:
                            classified["type"] = "info"
                        classified["date"] = msg.date.replace(tzinfo=timezone.utc)
                        catch_up_messages.append(classified)
            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"❌ Помилка підвантаження повідомлень з {username}: {e}")


async def get_catch_up_messages():
    return catch_up_messages
