# utils/filter.py
import re

# Наші дозволені регіони (нормалізація робиться тут же)
ALLOWED_DISTRICTS = {"броварський район", "київська область"}

# Пошукові ключі для гео і швидких загроз (для INFO з неофіційних)
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

# ------------------------------------------------------------
# ОФІЦІЙНІ ПОВІДОМЛЕННЯ @air_alert_ua: робимо кілька шаблонів
# Приклади:
#   "🔴 20:08 Повітряна тривога в Броварський район."
#   "🟢 00:12 Відбій тривоги в Київська область."
#   Можуть бути: тире/довге тире, інші розділові, жирність, новий рядок, тощо.
# ------------------------------------------------------------

# 1) базовий – як було
RE_BASE = re.compile(
    r"(повітряна\s+тривога|відбій\s+тривоги)\s+(?:в|у)\s+([^\n\.#!]+)",
    re.IGNORECASE | re.UNICODE,
)

# 2) допускаємо тире/дефіс між фразою і назвою регіону
RE_WITH_DASH = re.compile(
    r"(повітряна\s+тривога|відбій\s+тривоги)[^\n]*?(?:—|-|–)\s*([^\n\.#!]+)",
    re.IGNORECASE | re.UNICODE,
)

# 3) дуже лояльний: шукаємо фразу і далі або “в|у <регіон>” або просто беремо шматок до роздільника
RE_LOOSE = re.compile(
    r"(повітряна\s+тривога|відбій\s+тривоги)(?:[^\n]*?(?:в|у)\s+)?([^\n\.#!]+)",
    re.IGNORECASE | re.UNICODE,
)

# fallback по хештегу – інколи офіційний канал обов’язково ставить
HASHTAG_MAP = {
    "#броварський_район": "броварський район",
    "#київська_область": "київська область",
}

def _norm_district(d: str) -> str:
    d = (d or "").strip().lower()
    # прибираємо службові «м. », зайві пробіли, кінцеві крапки/коми/емодзі
    d = d.replace("м. ", "").strip()
    # відріжемо типові хвости
    d = re.sub(r"[#\.\!\,]+$", "", d).strip()
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
    """
    Пробуємо три варіанти парсингу з RE_*.
    Повертає (typ, district_norm) або None.
    """
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
    """
    Якщо регулярка не спрацювала – шукаємо офіційні хештеги
    і намагаємось вгадати тип з наявності ключових слів.
    """
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
        # якщо типової фрази нема – не ризикуємо
        return None
    return typ, found

def classify_message(text: str, url: str, source: str | None = None):
    """
    Повертає:
      - для офіційного @air_alert_ua: dict з type in {'alarm','all_clear'} або None якщо не наш регіон;
      - для інших: dict з type='info' + region_hit/rapid_hit + threat_type (якщо знайдено).
    """
    if not text:
        return None

    lower = text.lower()

    # ---------- 1) ОФІЦІЙНИЙ КАНАЛ ----------
    if source == "air_alert_ua":
        parsed = _try_official_parse(lower)
        if not parsed:
            # fallback по хештегу
            parsed = _try_hashtag_fallback(lower)

        if not parsed:
            # корисний дебаг у журналах, щоб бачити, що саме не зайшло
            print(f"[FILTER DEBUG] Official miss: {text[:140].replace(chr(10),' ')}")
            return None

        typ, district_norm = parsed

        # Працюємо тільки з нашими регіонами
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

    # ---------- 2) НЕофіційні канали → INFO ----------
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
