import re

def classify_message(text: str, source_url: str):
    lower = text.lower()

    result = {
        "text": text,
        "url": source_url,
        "id": hash(text + source_url)
    }

    # Географія: згадка про Бровари або Київську область
    brovary_keywords = ["бровар", "бровари", "броварський"]
    kyiv_keywords = ["київська область", "київщина", "міг", "ту", "київ"]

    if any(re.search(rf"\b{word}\b", lower) for word in brovary_keywords):
        result["district"] = "Броварський район"
    elif any(re.search(rf"\b{word}\b", lower) for word in kyiv_keywords):
        result["district"] = "Київська область"
    else:
        return None  # Ігноруємо повідомлення, не пов'язані з регіоном

    # Тип повідомлення: тривога або відбій
    if re.search(r"\bтривога\b", lower):
        return result
    if re.search(r"\bвідбій\b", lower):
        return result

    # Тип загрози
    threat_keywords = ["шахед", "ракета", "балістика", "іскандер", "х-101", "х-55", "загроза", "ту", "міг"]
    for threat in threat_keywords:
        if re.search(rf"\b{threat}\b", lower):
            result["threat_type"] = threat
            return result

    return result  # Якщо повідомлення з регіону, навіть без загрози — передаємо як новину під час тривоги
