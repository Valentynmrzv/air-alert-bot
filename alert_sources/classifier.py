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

    # Ключові слова для районів
    brovary_keywords = ["бровар", "бровари", "броварський"]
    kyiv_keywords = ["київська область", "київщина", "київська"]

    district = None
    if any(re.search(rf"\b{word}\b", lower) for word in brovary_keywords):
        district = "Броварський район"
    elif any(re.search(rf"\b{word}\b", lower) for word in kyiv_keywords):
        district = "Київська область"

    # Відбій тривоги
    if any(phrase in lower for phrase in ["відбій тривоги", "відбій повітряної тривоги", "відбій", "отбой"]):
        return {
            "district": district,
            "text": text,
            "url": source_url,
            "id": hash(text + source_url),
            "type": "all_clear"
        }

    # Повітряна тривога (фраза)
    if "повітряна тривога" in lower:
        return {
            "district": district,
            "text": text,
            "url": source_url,
            "id": hash(text + source_url),
            "type": "alarm"
        }

    # Глобальні загрози — тривога незалежно від району
    global_threats = ["міг", "авіація", "ракета", "іскандер", "балістика", "пуски", "зліт"]
    for threat in global_threats:
        if threat in lower:
            return {
                "district": None,
                "text": text,
                "url": source_url,
                "id": hash(text + source_url),
                "type": "alarm",
                "threat_type": threat
            }


    # Локальні загрози + район — тривога
    local_threats = [
        "шахед", "вибух", "вибухівка", "детонація", "детонації", "бомба", "бомбовий",
        "бомбардування", "розрив", "пошкодження", "руйнування", "удар", "вибуховий пристрій",
        "підрив", "підриви", "страйк", "снаряд", "артилерія", "міномет", "мінування",
        "мінометний", "обстріл", "знищення", "пожежа", "пожежі",
        "ппо", "зеніт", "зенітки", "протиповітряна оборона", "протиповітряна оборона", "бпла"
    ]
    for threat in local_threats:
        if re.search(rf"\b{threat}\b", lower):
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
                # Якщо локальна загроза, але район не знайдено — не класифікуємо
                return None

    # Якщо є район, але немає тривог — інформаційне
    if district:
        return {
            "district": district,
            "text": text,
            "url": source_url,
            "id": hash(text + source_url),
            "type": "info"
        }

    # Якщо нічого не релевантного
    return None
