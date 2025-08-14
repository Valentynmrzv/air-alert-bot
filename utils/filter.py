import re

ALLOWED_DISTRICTS = {"броварський район", "київська область"}

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

BRO_REVISOR_BONUS = {"на нас", "не летить", "летить", "не фіксується", "дорозвідка"}

# Більш «м’який» офіційний шаблон:
# ... (повітряна|відбій) ... (в|у)? ... <регіон до кінця рядка/роздільника>
OFFICIAL_RE = re.compile(
    r"(повітряна\s+тривога|відбій\s+тривоги)[^a-zа-яіїєґ]*?(?:в|у)?\s*([^\n\.#!]+)",
    re.IGNORECASE | re.UNICODE,
)

def _normalize_text(s: str) -> str:
    if not s:
        return ""
    t = s.lower()
    # NBSP та подібні у звичайний пробіл
    t = t.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
    # markdown / код
    t = t.replace("*", "").replace("`", "")
    # хештеги виду #Київська_область
    t = t.replace("_", " ").replace("#", " ")
    # прибираємо «сміття», але лишаємо букви/цифри/URL-символи
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

def classify_message(text: str, url: str, source: str | None = None):
    if not text:
        return None

    lower_raw = text.lower()
    lower = _normalize_text(text)

    # ---------- ОФІЦІЙНИЙ ----------
    if source == "air_alert_ua":
        m = OFFICIAL_RE.search(lower)
        phrase = None
        district_norm = None

        if m:
            phrase = m.group(1)
            district_norm = _norm_district(m.group(2))
        else:
            # Fallback 1: є ключова фраза і «броварський район»/«київська область» десь у тексті
            if "повітряна тривога" in lower or "відбій тривоги" in lower:
                if "броварський район" in lower:
                    phrase = "повітряна тривога" if "повітряна тривога" in lower else "відбій тривоги"
                    district_norm = "броварський район"
                elif "київська область" in lower:
                    phrase = "повітряна тривога" if "повітряна тривога" in lower else "відбій тривоги"
                    district_norm = "київська область"

        if not phrase or not district_norm:
            # раз у логах сипле None — допоможемо собі дебагом
            print("[FILTER DEBUG] Official miss:",
                  {"src": source, "norm": lower[:180], "raw": text[:120]})
            return None

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

    # ---------- НЕофіційні → INFO ----------
    region_hit = _is_region_hit(lower)
    rapid_hit = _is_rapid_hit(lower)
    threat = _guess_threat(lower)

    revisor_bonus = False
    if source == "bro_revisor":
        revisor_bonus = any(k in lower_raw for k in BRO_REVISOR_BONUS)
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
