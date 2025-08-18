# utils/filter.py
import re

ALLOWED_DISTRICTS = {"броварський район", "київська область"}

REGION_KEYWORDS = [
    "бровар", "бровари", "броварський",
    "київська область", "київщина", "київ",
    "княжич", "требух", "калинівк", "велика димер", "мала димер",
    "богданівк", "красилівк", "погреб", "зазим", "літк", "пухівк",
    "рожн", "світильн", "семиполк", "квітнев", "перемог", "гогол", "калит",
    "бориспіл", "троєщин", "лісов", "дарниц", "вишгород", "обух",
    "ірпін", "буча", "гостомел", "вишнев", "васильк", "березан", "баришівк",
]
RAPID_THREATS = [
    "балістик", "баллистик",
    "іскандер", "искандер",
    "кинжал",
    "миг-31", "міг-31", "миг 31", "міг 31", "mig-31", "mig 31",
    "зліт", "взлет", "старт",
    "пуск", "пуски", "запуск", "запуски",
]
THREAT_WORDS = [
    "шахед", "shahed", "дрон", "бпла", "ракета", "балістик", "іскандер", "кинжал",
]

# ------- ОФІЦІЙНІ ПОСТИ @air_alert_ua: кілька патернів -------
RE_BASE = re.compile(
    r"(повітряна\s+тривога|відбій\s+тривоги)\s+(?:в|у)\s+([^\n\.#!\*\)]+)",
    re.IGNORECASE | re.UNICODE,
)
RE_WITH_DASH = re.compile(
    r"(повітряна\s+тривога|відбій\s+тривоги)[^\n]*?(?:—|-|–)\s*([^\n\.#!\*\)]+)",
    re.IGNORECASE | re.UNICODE,
)
RE_LOOSE = re.compile(
    r"(повітряна\s+тривога|відбій\s+тривоги)(?:[^\n]*?(?:в|у)\s+)?([^\n\.#!\*\)]+)",
    re.IGNORECASE | re.UNICODE,
)

HASHTAG_MAP = {
    "#броварський_район": "броварський район",
    "#київська_область": "київська область",
}

def _norm_district(d: str) -> str:
    d = (d or "").strip().lower()
    d = d.replace("м. ", "").strip()
    # прибираємо хвости: пробіли, зірочки, хеш-символи, крапки, коми, окремі zero-width
    d = re.sub(r"[\s\*\#\.\!\,\u200d\ufe0f]+$", "", d).strip()
    return d

def _is_region_hit(lower: str) -> bool:
    return any(k in lower for k in REGION_KEYWORDS)

def _is_rapid_hit(lower: str) -> bool:
    return any(k in lower for k in RAPID_THREATS)

def _guess_threat(lower: str):
    for w in THREAT_WORDS:
        if w in lower:
            return w
    return None

def _try_official_parse(lower: str):
    for rx in (RE_BASE, RE_WITH_DASH, RE_LOOSE):
        m = rx.search(lower)
        if not m:
            continue
        phrase = (m.group(1) or "").lower()
        raw_district = (m.group(2) or "").strip()
        district_norm = _norm_district(raw_district)
        if "повітряна" in phrase:
            typ = "alarm"
        elif "відбій" in phrase:
            typ = "all_clear"
        else:
            continue
        return typ, district_norm
    return None

def _try_hashtag_fallback(lower: str):
    found = None
    for tag, norm in HASHTAG_MAP.items():
        if tag in lower:
            found = norm
            break
    if not found:
        return None
    if "повітряна тривога" in lower:
        typ = "alarm"
    elif "відбій тривоги" in lower:
        typ = "all_clear"
    else:
        return None
    return typ, found

def classify_message(text: str, url: str, source: str | None = None):
    if not text:
        return None

    lower = text.lower()

    # 1) Офіційний канал
    if source == "air_alert_ua":
        parsed = _try_official_parse(lower) or _try_hashtag_fallback(lower)
        if not parsed:
            print(f"[FILTER DEBUG] Official miss: {text[:180].replace(chr(10), ' ')}")
            return None
        typ, district_norm = parsed
        if district_norm not in ALLOWED_DISTRICTS:
            print(f"[FILTER DEBUG] Official other district: '{district_norm}'")
            return None
        return {
            "district": district_norm,
            "text": text,
            "url": url,
            "id": hash(text + url),
            "type": typ,
        }

    # 2) Неофіційні → info
    region_hit = _is_region_hit(lower)
    rapid_hit = _is_rapid_hit(lower)
    threat = _guess_threat(lower)

    return {
        "district": None,
        "text": text,
        "url": url,
        "id": hash(text + url),
        "type": "info",
        "region_hit": region_hit,
        "rapid_hit": rapid_hit,
        "threat_type": threat,
        "source": source,
    }
