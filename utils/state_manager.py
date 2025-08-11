import json
import os

STATE_PATH = os.getenv("STATE_PATH", "state.json")

_DEFAULT_STATE = {
    "sent": [],
    "status_message_id": None,
    "alert_active": False,
    "threat_sent": [],
    "alert_started_at": {
        "Броварський район": None,
        "Київська область": None
    },
    "start_message_id": None,
    "timer_message_id": None,
    "last_ids": {}
}


def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return _DEFAULT_STATE.copy()
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # додамо відсутні ключі
            changed = False
            for k, v in _DEFAULT_STATE.items():
                if k not in data:
                    data[k] = v
                    changed = True
            if changed:
                save_state(data)
            return data
    except Exception:
        return _DEFAULT_STATE.copy()


def save_state(state: dict):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def ensure_state_defaults(state: dict, defaults: dict) -> bool:
    changed = False
    for k, v in defaults.items():
        if k not in state:
            state[k] = v
            changed = True
    return changed
