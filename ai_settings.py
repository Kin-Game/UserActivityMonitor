from __future__ import annotations

from pathlib import Path
from typing import Dict, Any
import json

AI_SETTINGS_PATH = Path("data/ai_settings.json")

DEFAULT_AI_SETTINGS: Dict[str, Any] = {

    "mode": "hybrid",
 
    "use_history": True,
}

def load_ai_settings() -> Dict[str, Any]:
    cfg = dict(DEFAULT_AI_SETTINGS)
    try:
        if AI_SETTINGS_PATH.is_file():
            with AI_SETTINGS_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f) or {}
            if isinstance(data, dict):
                cfg.update(data)
    except Exception:

        pass
    return cfg


def save_ai_settings(cfg: Dict[str, Any]) -> None:
    data = dict(DEFAULT_AI_SETTINGS)
    if isinstance(cfg, dict):
        data.update(cfg)

    AI_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AI_SETTINGS_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
