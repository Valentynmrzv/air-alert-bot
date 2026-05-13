ALLOWED_DISTRICTS = {"броварський район", "київська область"}

REGION_KEYWORDS = [
    "бровари", "броварський", "броварського", "броварщин",
    "київщина", "київська область", "київ",
    "княжичі", "требухів", "калинівка", "велика димерка", "мала димерка",
    "богданівка", "красилівка", "погреби", "зазим'я", "зазимя", "літки", "литки", "пухівка",
    "рожни", "світильня", "семиполки", "квітневе", "перемога", "гоголів", "калита",
    "русанів", "русанов", "русанове", "плоске", "шевченкове", "заворичі",
    "бориспіль", "березань", "баришівк", "баришевк", "вишгород", "обухів",
    "ірпін", "буча", "гостомел", "вишневе", "васильків",
]

RAPID_THREATS = [
    "баліст", "баллист", "іскандер", "искандер", "кинджал",
    "міг-31", "миг-31", "міг 31", "миг 31", "mig-31", "mig 31", "міг", "миг",
    "зліт", "взлёт", "взлет", "старт", "пуск", "пуски", "запуск", "запуски",
    "ппо", "пво",
]

THREAT_WORDS = [
    "шахед", "shahed", "мопед", "мопеди",
    "дрон", "дрони", "бпла", "безпілот",
    "ракета", "ракети", "ракетн", "крилат",
    "баліст", "баллист", "іскандер", "искандер", "кинджал",
    "пуск", "запуск", "зліт", "приліт", "вибух", "влучан", "ппо", "пво",
]

HASHTAG_MAP = {
    "#броварський_район": "броварський район",
    "#київська_область": "київська область",
}


def _is_region_hit(lower: str) -> bool:
    return any(k in lower for k in REGION_KEYWORDS)


def _is_rapid_hit(lower: str) -> bool:
    return any(k in lower for k in RAPID_THREATS)


def _guess_threat(lower: str):
    for w in THREAT_WORDS:
        if w in lower:
            return w
    return None


def _classify_official_type(lower: str):
    if "повітряна тривога" in lower:
        return "alarm"
    if "відбій тривоги" in lower or "відбій повітряної тривоги" in lower:
        return "all_clear"
    return None


def _extract_allowed_official_district(lower: str):
    for tag, norm in HASHTAG_MAP.items():
        if tag in lower:
            return norm

    for district in ALLOWED_DISTRICTS:
        if district in lower:
            return district

    return None


def classify_message(text: str, url: str, source: str | None = None):
    if not text:
        return None

    lower = text.lower()

    if source == "air_alert_ua":
        typ = _classify_official_type(lower)
        district = _extract_allowed_official_district(lower)

        if typ and district:
            return {
                "district": district,
                "text": text,
                "url": url,
                "id": hash(text + url),
                "type": typ,
            }

        if typ and not district:
            print(f"[FILTER DEBUG] Official other district: {text[:180].replace(chr(10), ' ')}")
            return None

        print(f"[FILTER DEBUG] Official miss: {text[:180].replace(chr(10), ' ')}")
        return None

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
