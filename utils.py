import json
from datetime import datetime


def now():
    return datetime.now()


def load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        
def format_duration_human(seconds: int) -> str:
    if seconds is None:
        seconds = 0
    if seconds < 0:
        seconds = 0

    seconds = int(seconds)

 
    if seconds < 60:
        return f"{seconds} с"

    minutes = seconds // 60
    sec = seconds % 60


    if seconds < 3600:
        if sec:
            return f"{minutes} хв {sec} с"
        return f"{minutes} хв"

    hours = minutes // 60
    rem_min = minutes % 60


    if rem_min:
        return f"{hours} год {rem_min} хв"
    return f"{hours} год"
