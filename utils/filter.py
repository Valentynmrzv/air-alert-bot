import re

# Наші дозволені регіони (нормалізація робиться тут же)
ALLOWED_DISTRICTS = {"броварський район", "київська область"}

# Пошукові ключі для гео і швидких загроз
REGION_KEYWORDS = [
    "бровар", "бровари", "броварський",
    "київська область", "київщина", "київ",
    "княжич", "требух", "калинівк", "велика димер", "мала димер",
    "богданівк", "красилівк", "погреби", "зазим", "літки", "пухівк",
    "рожни", "світильн", "семиполк", "квітнев", "перемог", "гогол", "калита",
    "бориспіл", "троєщин", "лісов", "дарниц", "вишгород", "обух", "ірпін", "буча",
    "гостомел", "вишнев", "васильк", "березан", "баришівк",
]

RAPID_THREATS = [
    # швидкі загрози / балістика / носії
    "балістик", "баллистик",
    "іскандер", "искандер",
    "кинжал", "кинжала", "миг-31", "міг-31", "миг 31", "міг 31",
    "mig-31", "mig 31",
    "зліт", "взлет",
    # часто в новинах:
    "пуски", "пуск", "запуск", "запуски",
]

THREAT_WORDS = [
    # для довідки/тега "threat_type" (не обов’язково повний)
    "шахед", "shahed", "дрон", "бпла", "ракета", "балістик", "іскандер", "кинжал",
]

# офіційний формат @air_alert_ua:
# "🔴 21:05 Повітряна тривога в Броварський район." / "🟢 00:12 Відбій тривоги в Київська область."
# Може бути крапка/знак/перенос далі, тому вирізаємо до першого роздільника.
OFFICIAL_RE = re.compile(
    r"(повітряна\s+тривога|відбій\s+тривоги)\s+в\s+([^\n\.#!]+)",
    re.IGNORECASE | re.UNICODE,
)

def _norm_district(d: str) -> str:
    d = (d or "").strip().lower()
    # прибрати службові крапки та зайві пробіли типу "м. київ"
    d = d.replace("м. ", "").strip()
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

def classify_message(text: str, url: str, source: str | None = None):
    """
    Повертає:
      - для офіційного @air_alert_ua: dict з type in {'alarm','all_clear'} або None якщо не наш регіон;
      - для інших: dict з type='info' + region_hit/rapid_hit + threat_type (якщо знайдено).
    """
    if not text:
        return None

    lower = text.lower()

    # 1) ОФІЦІЙНИЙ канал: шукаємо "повітряна тривога/відбій тривоги в <регіон>"
    if source == "air_alert_ua":
        m = OFFICIAL_RE.search(lower)
        if not m:
            return None

        phrase = m.group(1)  # "повітряна тривога" або "відбій тривоги"
        district_raw = m.group(2)
        district_norm = _norm_district(district_raw)

        # Працюємо тільки з нашими регіонами
        if district_norm not in ALLOWED_DISTRICTS:
            return None

        typ = "alarm" if "повітряна" in phrase else "all_clear"

        return {
            "district": district_norm,
            "text": text,
            "url": url,
            "id": hash(text + url),
            "type": typ,
            # офіційні пости не тегуємо region/rapid — це не потрібно
        }

    # 2) НЕофіційні канали → INFO
    region_hit = _is_region_hit(lower)
    rapid_hit = _is_rapid_hit(lower)
    threat = _guess_threat(lower)

    return {
        "district": None,              # район не з офіційного — не довіряємо
        "text": text,
        "url": url,
        "id": hash(text + url),
        "type": "info",
        "region_hit": region_hit,
        "rapid_hit": rapid_hit,
        "threat_type": threat,
        "source": source,
    }
