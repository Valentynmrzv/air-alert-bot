import re

BROVARY_KEYWORDS = ["бровар", "бровари", "броварський"]
KYIVREGION_KEYWORDS = ["київська область", "київщина"]

def _district_from_text(lower: str):
    if any(re.search(rf"\b{w}\b", lower) for w in BROVARY_KEYWORDS):
        return "Броварський район"
    if any(re.search(rf"\b{w}\b", lower) for w in KYIVREGION_KEYWORDS):
        return "Київська область"
    return None


def classify_message(text: str, source_url: str):
    """
    Повертає:
      - type: 'alarm' | 'all_clear' | 'info'
      - district: 'Броварський район' | 'Київська область' | None
      - threat_type: str | None
      - text, url, id
    """
    if not text:
        return None

    lower = text.lower()
    district = _district_from_text(lower)

    # Відбій (тільки якщо наш район визначений)
    all_clear_patterns = [
        r"відбій\s+тривоги",
        r"відбій\s+повітряної\s+тривоги",
        r"\bвідбій\b",
        r"\bотбой\b",
        r"тривога\s+(скасована|закінчена|відмінена)",
        r"закінчення\s+тривоги"
    ]
    for pattern in all_clear_patterns:
        if re.search(pattern, lower) and district is not None:
            return {
                "district": district,
                "text": text,
                "url": source_url,
                "id": hash(text + source_url),
                "type": "all_clear"
            }

    # Пряма згадка тривоги (тільки якщо район наш або є загроза)
    if "повітряна тривога" in lower and district is not None:
        return {
            "district": district,
            "text": text,
            "url": source_url,
            "id": hash(text + source_url),
            "type": "alarm"
        }

    # Глобальні загрози (можемо сигналізувати alarm навіть без району,
    # але у main.py все одно фільтруємо лише наші райони)
    global_threats = ["міг", "авіація", "ракета", "іскандер", "балістик", "пуски", "пуск", "зліт", "кинжал", "калібр"]
    for threat in global_threats:
        if re.search(rf"\b{threat}\w*\b", lower):
            return {
                "district": district,
                "text": text,
                "url": source_url,
                "id": hash(text + source_url),
                "type": "alarm",
                "threat_type": threat
            }

    # Локальні загрози — враховуємо тільки якщо район наш
    local_threats = [
        "шахед", "вибух", "детонац", "бомба", "удар",
        "обстріл", "артилер", "міномет", "бпла", "ппо", "зеніт"
    ]
    for threat in local_threats:
        if re.search(rf"\b{threat}\w*\b", lower):
            if district:
                return {
                    "district": district,
                    "text": text,
                    "url": source_url,
                    "id": hash(text + source_url),
                    "type": "alarm",
                    "threat_type": threat
                }
            else:
                return None

    # Якщо є район, але без тривоги — інфо для нього
    if district:
        return {
            "district": district,
            "text": text,
            "url": source_url,
            "id": hash(text + source_url),
            "type": "info"
        }

    return None
