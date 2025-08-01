def classify_message(text: str, source_url: str):
    lower = text.lower()

    # Базовий об'єкт
    result = {
        "text": text,
        "url": source_url,
        "id": hash(text + source_url)
    }

    # Географія
    if "бровар" in lower:
        result["district"] = "Броварський район"
    elif "київська область" in lower or "київщина" in lower:
        result["district"] = "Київська область"
    else:
        return None  # Не стосується нашого регіону

    # Типи повідомлень
    if "тривога" in lower:
        return result

    if "відбій" in lower:
        return result

    for threat in ["шахед", "ракета", "балістика", "іскандер", "х-101", "х-55"]:
        if threat in lower:
            result["threat_type"] = threat
            return result

    return None  # Якщо немає ключових даних
