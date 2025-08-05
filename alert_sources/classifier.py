def classify_message(text: str, source_url: str):
    lower = text.lower()

    # Базовий об'єкт
    result = {
        "text": text,
        "url": source_url,
        "id": hash(text + source_url)
    }

    # Географія
    if any(word in lower for word in ["бровар", "бровари", "броварський"]):
        result["district"] = "Броварський район"
    elif any(word in lower for word in ["київська область", "київщина"]):
        result["district"] = "Київська область"
    else:
        return None  # Не стосується нашого регіону

    # Типи повідомлень
    if "тривога" in lower:
        return result

    if "відбій" in lower:
        return result

    # Типи загроз (розширений список)
    threats = [
        "шахед", "ракета", "баліст", "іскандер", "кінджал",
        "х-101", "х-55", "х-22", "х-32", "калібр", "онікс",
        "ту", "ту-95", "ту-160", "міг", "міг-31", "миг", "mig"
    ]
    for threat in threats:
        if threat in lower:
            result["threat_type"] = threat
            return result

    return None  # Якщо немає ключових даних
