import re

def classify_alert_message(text: str, url: str):
    """
    Класифікує офіційні повідомлення тривоги та відбою
    у форматі каналу @air_alert_ua, наприклад:
    "Повітряна тривога в Броварський район"
    "Відбій тривоги в Київська область"

    Повертає словник із ключами:
    - type: 'alarm' або 'all_clear'
    - district: район
    - text: оригінальний текст
    - url: посилання на повідомлення
    - id: унікальний ідентифікатор (хеш)
    """
    if not text:
        return None

    alarm_match = re.search(r"повітряна тривога в ([\w\s\-]+)", text, re.I)
    all_clear_match = re.search(r"відбій тривоги в ([\w\s\-]+)", text, re.I)

    if alarm_match:
        return {
            "type": "alarm",
            "district": alarm_match.group(1).strip(),
            "text": text,
            "url": url,
            "id": hash(text + url)
        }
    if all_clear_match:
        return {
            "type": "all_clear",
            "district": all_clear_match.group(1).strip(),
            "text": text,
            "url": url,
            "id": hash(text + url)
        }
    return None


def classify_message(text: str, source_url: str):
    """
    Класифікує повідомлення за типом (тривога/відбій/info), районом і загрозою.
    Повертає словник із ключами:
    - district: район (наприклад, 'Броварський район' або 'Київська область')
    - type: 'alarm', 'all_clear' або 'info' (тривога, відбій або інформація)
    - threat_type: (опційно) тип загрози, напр. ракета, балістика
    - text: оригінальний текст
    - url: посилання на повідомлення
    - id: унікальний ідентифікатор (хеш)

    Якщо повідомлення не релевантне — повертає None.
    """
    if not text:
        return None

    lower = text.lower()

    brovary_keywords = ["бровар", "бровари", "броварський"]
    kyiv_keywords = ["київська область", "київщина", "київ"]

    district = None
    if any(re.search(rf"\b{word}\b", lower) for word in brovary_keywords):
        district = "Броварський район"
    elif any(re.search(rf"\b{word}\b", lower) for word in kyiv_keywords):
        district = "Київська область"

    if not district:
        return None

    result = {
        "district": district,
        "text": text,
        "url": source_url,
        "id": hash(text + source_url)
    }

    # Визначаємо тип повідомлення
    if "повітряна тривога" in lower or "тривога" in lower:
        result["type"] = "alarm"
    elif "відбій" in lower:
        result["type"] = "all_clear"
    else:
        result["type"] = "info"

    # Перевірка на тип загрози
    threat_keywords = ["шахед", "ракета", "балістика", "іскандер", "х-101", "х-55"]
    for threat in threat_keywords:
        if threat in lower:
            result["threat_type"] = threat
            break

    return result
