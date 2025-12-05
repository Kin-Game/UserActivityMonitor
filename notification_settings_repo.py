from __future__ import annotations
from pathlib import Path
import json
from typing import Dict, Any


class NotificationSettingsRepository:


    def __init__(self, path: Path | None = None):
        if path is None:
            base = Path("data")
            base.mkdir(exist_ok=True)
            path = base / "notifications.json"
        self.path = path

        self.defaults: Dict[str, Any] = {
            "enabled": True,
            "warning_enabled": True,
            "over_enabled": True,
            "min_live_seconds": 60,

            "warning_threshold": 0.8,
            "over_threshold": 1.0,
            "cooldown_warning_sec": 20 * 60,
            "cooldown_over_sec": 5 * 60,
        }


    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return dict(self.defaults)

        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return dict(self.defaults)

        cfg = dict(self.defaults)
        cfg.update(data or {})
        return cfg

    def save(self, cfg: Dict[str, Any]) -> None:
        data = dict(self.defaults)
        data.update(cfg or {})
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
