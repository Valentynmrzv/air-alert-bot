from utils.filter import classify_message


def test_single_district_alarm():
    text = (
        "17:34 Повітряна тривога в Броварський район\n"
        "Слідкуйте за подальшими повідомленнями.\n"
        "#Броварський_район"
    )

    result = classify_message(text, "https://t.me/air_alert_ua/1", source="air_alert_ua")

    assert result is not None
    assert result["type"] == "alarm"
    assert result["district"] == "броварський район"


def test_multi_district_alarm_with_bullets():
    text = (
        "15:47 Повітряна тривога в \n"
        "• Вишгородський район\n"
        "• Бучанський район\n"
        "• Обухівський район\n"
        "• Фастівський район\n"
        "• Білоцерківський район\n"
        "• Бориспільський район\n"
        "• Броварський район\n"
        "Слідкуйте за подальшими повідомленнями.\n"
        "#Вишгородський_район #Бучанський_район #Обухівський_район "
        "#Фастівський_район #Білоцерківський_район #Бориспільський_район "
        "#Броварський_район"
    )

    result = classify_message(text, "https://t.me/air_alert_ua/2", source="air_alert_ua")

    assert result is not None
    assert result["type"] == "alarm"
    assert result["district"] == "броварський район"


def test_single_district_all_clear():
    text = (
        "18:05 Відбій повітряної тривоги в Броварський район\n"
        "Можете залишити укриття.\n"
        "#Броварський_район"
    )

    result = classify_message(text, "https://t.me/air_alert_ua/3", source="air_alert_ua")

    assert result is not None
    assert result["type"] == "all_clear"
    assert result["district"] == "броварський район"


def test_multi_district_all_clear_with_hashtag_fallback():
    text = (
        "18:10 Відбій повітряної тривоги в \n"
        "• Вишгородський район\n"
        "• Броварський район\n"
        "Можете залишити укриття.\n"
        "#Вишгородський_район #Броварський_район"
    )

    result = classify_message(text, "https://t.me/air_alert_ua/4", source="air_alert_ua")

    assert result is not None
    assert result["type"] == "all_clear"
    assert result["district"] == "броварський район"
