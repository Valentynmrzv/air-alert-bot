import re

# Наші дозволені регіони (нормалізація робиться тут же)
ALLOWED_DISTRICTS = {"броварський район", "київська область"}

# Пошукові ключі для гео і швидких загроз
REGION_KEYWORDS = [
    "бровар", "бровари", "броварськ",
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
    "кинжал", "миг-31", "міг-31", "миг 31", "міг 31", "mig-31", "mig 31", "міг", "миг",
    "зліт", "взлет",
    "пуски", "пуск", "запуск", "запуски", "старт",
]

THREAT_WORDS = [
    "шахед", "shahed", "дрон", "бпла", "ракета", "балістик", "іскандер", "кинжал",
]

# Бонус-фрази для @bro_revisor
BRO_REVISOR_BONUS = {"на нас", "не летить", "летить", "не фіксується", "дорозвідка"}

# Офіційний формат @air_alert_ua: допускаємо "в" або "у" і «шум» у тексті
OFFICIAL_RE = re.compile(
    r"(повітряна\s+тривога|відбій\s+тривоги)\s+(?:в|у)\s+([^\n\.#!]+)",
    re.IGNORECASE | re.UNICODE,
)

# --- допоміжні ---

def _normalize_text(s: str) -> str:
    """Прибрати жирний/підкреслення/емодзі/зайві символи, зберегти URL та слова."""
    if not s:
        return ""
    t = s.lower()
    t = t.replace("_", " ")                  # #Київська_область -> Київська область
    t = t.replace("*", "").replace("`", "")  # прибрати markdown
    t = re.sub(r"[#]", " ", t)               # решітку як розділювач
    # прибрати «сміття», але лишити букви/цифри/пробіли/URL-символи
    t = re.sub(r"[^\w\s:/\.\-\(\)]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def _norm_district(d: str) -> str:
    d = (d or "").strip().lower()
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

# --- головна ---

def classify_message(text: str, url: str, source: str | None = None):
    """
    Повертає:
      - для офіційного @air_alert_ua: dict з type in {'alarm','all_clear'} або None якщо не наш регіон;
      - для інших: dict з type='info' + region_hit/rapid_hit/revisor_bonus + threat_type (якщо знайдено).
    """
    if not text:
        return None

    lower_raw = text.lower()
    lower = _normalize_text(text)

    # 1) ОФІЦІЙНИЙ канал: шукаємо "повітряна/відбій ... (в|у) <регіон>"
    if source == "air_alert_ua":
        m = OFFICIAL_RE.search(lower)
        if not m:
            # fallback: інколи є лише хештег регіону без "в|у"
            if "броварський район" in lower:
                phrase = "повітряна тривога" if "повітряна тривога" in lower else ("відбій тривоги" if "відбій тривоги" in lower else None)
                if phrase:
                    district_norm = "броварський район"
                else:
                    return None
            elif "київська область" in lower:
                phrase = "повітряна тривога" if "повітряна тривога" in lower else ("відбій тривоги" if "відбій тривоги" in lower else None)
                if phrase:
                    district_norm = "київська область"
                else:
                    return None
            else:
                return None
        else:
            phrase = m.group(1)
            district_raw = m.group(2)
            district_norm = _norm_district(district_raw)

        if district_norm not in ALLOWED_DISTRICTS:
            return None

        typ = "alarm" if "повітряна" in phrase else "all_clear"
        return {
            "district": district_norm,
            "text": text,
            "url": url,
            "id": hash(("official", text, url)),
            "type": typ,
        }

    # 2) НЕофіційні канали → INFO
    region_hit = _is_region_hit(lower)
    rapid_hit = _is_rapid_hit(lower)
    threat = _guess_threat(lower)

    revisor_bonus = False
    if source == "bro_revisor":
        # бонус — короткі фрази, що у них означають місцеву (для нас) релевантність
        revisor_bonus = any(k in lower_raw for k in BRO_REVISOR_BONUS)
        # якщо є бонус — вважаємо це локально важливим
        if revisor_bonus and not region_hit:
            region_hit = True

    return {
        "district": None,
        "text": text,
        "url": url,
        "id": hash(("info", text, url)),
        "type": "info",
        "region_hit": region_hit,
        "rapid_hit": rapid_hit,
        "revisor_bonus": revisor_bonus,
        "threat_type": threat,
        "source": source,
    }
