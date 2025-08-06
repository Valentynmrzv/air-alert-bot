import json
import os

STATE_FILE = "state.json"

def load_state():
    if not os.path.exists(STATE_FILE):
        state = {
            "sent": [],
            "start_message_id": None,
            "timer_message_id": None,
            "alert_active": False,      # Додано
            "threat_sent": []           # Додано
        }
        save_state(state)
        return state
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Помилка читання стану: {e}")
        return {
            "sent": [],
            "start_message_id": None,
            "timer_message_id": None,
            "alert_active": False,
            "threat_sent": []
        }

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"❌ Помилка запису стану: {e}")