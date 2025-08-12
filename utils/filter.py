# utils/filter.py
import re
from typing import Optional, Dict

# Нормалізація назв локацій з офіційного каналу
_AIRALERT_MAP = {
    "київська область": "Київська область",
    "київська обл": "Київська область",
    "київщина": "Київська область",
    "броварський район": "Броварський район",
    "броварський р-н": "Броварський район",
    "броварський": "Броварський район",
    # місто Київ — завжди ігноруємо для автотривоги
    "м. київ": "м. Київ",
    "київ": "м. Київ",
    "город киев": "м. Київ",
    "м київ": "м. Київ",
}

# лише ці два регіони запускають/знімають тривогу
_ALLOWED_DISTRICTS = {"Київська область", "Броварський район"}

# суворий парсер для @air_alert_ua
_AIRALERT_RE = re.compile(
    r"(повітряна\s+тривога|відбій\s+тривоги)\s+в\s+([^\n#\.\!\r]+)",
    re.IGNORECASE | re.UNICODE,
)

def _normalize_location(raw: str) -> str:
    key = raw.strip().lower()
    key = re.sub(r"\s+", " ", key)
    return _AIRALERT_MAP.get(key, raw.strip())

def _airalert_classify(text: str, url: str) -> Optional[Dict]:
    m = _AIRALERT_RE.search(text or "")
    if not m:
        return None
    typ, loc = m.group(1), m.group(2)
    loc_norm = _normalize_location(loc)

    # ігноруємо м. Київ повністю
    if loc_norm == "м. Київ":
        return None

    if loc_norm not in _ALLOWED_DISTRICTS:
        return None

    evt_type = "alarm" if "повітряна" in typ.lower() else "all_clear"
    return {
        "district": loc_norm,
        "text": text,
        "url": url,
        "id": hash(text + url),
        "type": evt_type,
    }

# загрози/регіональні підказки для неофіційних каналів (info)
_THREATS = [
    "🛵", "🚀", "💥", "✈️", "💣", "🛩️", "🎯", "🧨", "🚨", "🔥",
    "шахед", "шахеди", "shahed", "шаhed", "мопед", "мопеди",
    "дрон", "дрони", "бпла", "безпілотник", "безпілотники",
    "ракета", "ракети", "ракетн",
    "балістика", "балістичн",
    "іскандер", "кинжал", "калібр",
    "пуск", "пуски", "запуск", "запуски",
    "зліт", "зльот", "авіація",
    "удар", "удари", "обстріл", "обстріли",
    "вибух", "вибухи", "приліт", "прильот", "прильоти",
    "сирена", "небезпека", "загроза",
    "шахедов", "дронов", "беспилотник", "беспилотники",
    "ракеты", "ракетн", "баллистик", "искандер", "калибр",
    "взлет", "авиация",
    "удар", "удары", "обстрел", "обстрелы",
    "взрыв", "взрывы", "прилет", "прилеты",
    "опасност", "угроза",
]

_REGION_HINTS = [
    "бровар", "бровари", "броварський", "київська область", "київщина", "київ",
    # прилеглі топоніми — як хінт для інформаційного повідомлення
    "княжич", "требух", "калинівк", "велика димер", "мала димер",
    "богданівк", "красилівк", "погреби", "зазим", "літки", "пухівк",
    "рожни", "світильн", "семиполк", "квітнев", "перемог", "гогол", "калита",
    "бориспіл", "троєщин", "лісов", "дарниц", "вишгород", "обух", "ірпін", "буча",
    "гостомел", "вишнев", "васильк", "березан", "баришівк",
]

# спец-слово саме для bro_revisor (додатковий тригер)
_BRO_REVISOR_HINTS = ["на нас"]

def _info_from_unofficial(text: str, url: str, source: Optional[str]) -> Optional[Dict]:
    low = (text or "").lower()

    # bro_revisor: пропускаємо, якщо є "на нас"
    if source and source.lower() == "bro_revisor":
        if any(h in low for h in _BRO_REVISOR_HINTS):
            return {
                "district": None,
                "text": text,
                "url": url,
                "id": hash(text + url),
                "type": "info",
            }
        # якщо не збіглося — далі працює загальна логіка нижче

    # Для інших каналів (і bro_revisor теж): достатньо АБО регіонального хінта, АБО загрози
    if any(r in low for r in _REGION_HINTS) or any(t in low for t in _THREATS):
        return {
            "district": None,
            "text": text,
            "url": url,
            "id": hash(text + url),
            "type": "info",
        }
    return None

def classify_message(text: str, url: str, source: Optional[str] = None) -> Optional[Dict]:
    """
    - Для @air_alert_ua: повертає 'alarm'/'all_clear' тільки для Київської області або Броварського району.
      'м. Київ' та інші локації ігноруються (None).
    - Для інших каналів (у т.ч. bro_revisor): повертає 'info', якщо є ХОЧА Б один з ознак:
        • будь-який топонім з REGION_HINTS, АБО
        • будь-яка загроза з THREATS,
        • для bro_revisor додатково тригер: фраза "на нас".
      Пересилка в канал відбувається в main.py лише під час активної тривоги.
    """
    if not text:
        return None

    if source and source.lower() == "air_alert_ua":
        return _airalert_classify(text, url)

    return _info_from_unofficial(text, url, source)
