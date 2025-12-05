from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

CATEGORIES: List[str] = [
    "work",
    "games",
    "media",
    "browsing",
    "communication",
    "social",
    "education",
    "other",
]


# Базові ліміти (хв/день) для профілю за змовчуванням
DEFAULT_LIMITS_MIN: Dict[str, int] = {
    "work": 480,          # 8 год
    "games": 120,
    "media": 120,
    "browsing": 120,
    "communication": 180,
    "social": 60,
    "education": 240,
    "other": 60,
}


# ---------------------------------------------------------------------------
#   Моделі
# ---------------------------------------------------------------------------

@dataclass
class CategoryLimit:
    enabled: bool = True
    limit_minutes: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "CategoryLimit":
        return cls(
            enabled=bool(data.get("enabled", False)),
            limit_minutes=int(data.get("limit_minutes", 0)),
        )

    def to_dict(self) -> dict:
        return {
            "enabled": bool(self.enabled),
            "limit_minutes": int(self.limit_minutes),
        }


@dataclass
class LimitProfile:
    name: str
    limits: Dict[str, CategoryLimit] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: dict) -> "LimitProfile":
        raw_limits = data.get("limits", {}) or {}
        limits: Dict[str, CategoryLimit] = {}
        for cat in CATEGORIES:
            cfg = raw_limits.get(cat, {})
            limits[cat] = CategoryLimit.from_dict(cfg)
        return cls(name=name, limits=limits)

    def to_dict(self) -> dict:
        return {
            "limits": {cat: self.limits[cat].to_dict() for cat in CATEGORIES},
        }


# ---------------------------------------------------------------------------
#   Репозиторій профілів лімітів
# ---------------------------------------------------------------------------

class CategoryLimitsRepository:


    WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    def __init__(self, path: Optional[str | Path] = None) -> None:
        base_dir = Path(__file__).resolve().parent.parent
        default_path = base_dir / "data" / "category_limits.json"

        self.path: Path = Path(path) if path is not None else default_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self._data: dict = self._load()

    # ----------------- базова робота з файлом -----------------

    def _load(self) -> dict:
        if not self.path.exists():
            data = self._make_default_data()
            self._save_raw(data)
            return data

        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = self._make_default_data()

        # Мінімальна валідація
        if "profiles" not in data or not isinstance(data["profiles"], dict):
            data = self._make_default_data()

        return data

    def _save_raw(self, data: dict) -> None:
        tmp_path = self.path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path.replace(self.path)

    def _make_default_data(self) -> dict:
        limits = {
            cat: CategoryLimit(enabled=True, limit_minutes=DEFAULT_LIMITS_MIN.get(cat, 60)).to_dict()
            for cat in CATEGORIES
        }

        return {
            "active_profile": "standard",
            "profiles": {
                "standard": {
                    "limits": limits,
                }
            },
            "weekly_schedule": {
                key: "standard" for key in self.WEEKDAY_KEYS
            },
        }

    def _ensure_profile_exists(self, name: str) -> LimitProfile:
        profiles = self._data.setdefault("profiles", {})
        if name not in profiles:
            base = profiles.get("standard") or {
                "limits": {
                    cat: CategoryLimit(enabled=True, limit_minutes=DEFAULT_LIMITS_MIN.get(cat, 60)).to_dict()
                    for cat in CATEGORIES
                }
            }
            profiles[name] = base
        return LimitProfile.from_dict(name, profiles[name])

    # ----------------- вибір профілю -----------------

    def get_active_profile_name(self, for_date: Optional[date] = None) -> str:

        profiles = self._data.get("profiles", {}) or {}
        if not profiles:
            self._data = self._make_default_data()
            profiles = self._data["profiles"]

        # 1) За розкладом
        if for_date is not None:
            idx = for_date.weekday()  
            key = self.WEEKDAY_KEYS[idx]
            schedule = self._data.get("weekly_schedule", {}) or {}
            prof = schedule.get(key)
            if prof in profiles:
                return prof

        # 2) Явно активний профіль
        prof = self._data.get("active_profile") or "standard"
        if prof in profiles:
            return prof

        # 3) Будь-який наявний
        return next(iter(profiles.keys()))

    def set_active_profile(self, name: str) -> None:
        profiles = self._data.get("profiles", {}) or {}
        if name not in profiles:
            raise ValueError(f"Unknown profile '{name}'")
        self._data["active_profile"] = name
        self._save_raw(self._data)



    def get_all_limits(self) -> Dict[str, dict]:

        profile_name = self.get_active_profile_name(date.today())
        prof = self._ensure_profile_exists(profile_name)

        return {cat: prof.limits[cat].to_dict() for cat in CATEGORIES}

    def save_limits(self, limits: Dict[str, dict]) -> None:
  
        profile_name = self.get_active_profile_name()
        self.save_limits_for_profile(profile_name, limits)

    # ---- робота з конкретним профілем ----

    def get_limits_for_profile(self, profile_name: str) -> Dict[str, dict]:
        prof = self._ensure_profile_exists(profile_name)
        return {cat: prof.limits[cat].to_dict() for cat in CATEGORIES}

    def save_limits_for_profile(self, profile_name: str, limits: Dict[str, dict]) -> None:
        profiles = self._data.setdefault("profiles", {})

        prof = self._ensure_profile_exists(profile_name)

        for cat in CATEGORIES:
            cfg = limits.get(cat, {})
            prof.limits[cat] = CategoryLimit.from_dict(cfg)

        profiles[profile_name] = prof.to_dict()
        self._data["profiles"] = profiles
        self._save_raw(self._data)


    def list_profiles(self) -> List[str]:
        profiles = self._data.get("profiles", {}) or {}
        return sorted(profiles.keys())

    def create_profile(self, name: str, base: Optional[str] = None) -> None:
        profiles = self._data.setdefault("profiles", {})
        if name in profiles:
            raise ValueError(f"Profile '{name}' already exists")

        if base and base in profiles:
            base_prof = LimitProfile.from_dict(base, profiles[base])
        else:
            base_prof = LimitProfile(
                name=name,
                limits={
                    cat: CategoryLimit(enabled=True, limit_minutes=DEFAULT_LIMITS_MIN.get(cat, 60))
                    for cat in CATEGORIES
                },
            )

        profiles[name] = base_prof.to_dict()
        self._save_raw(self._data)

    def rename_profile(self, old_name: str, new_name: str) -> None:
        if old_name == new_name:
            return

        profiles = self._data.setdefault("profiles", {})
        if old_name not in profiles:
            raise ValueError(f"Profile '{old_name}' does not exist")
        if new_name in profiles:
            raise ValueError(f"Profile '{new_name}' already exists")

        profiles[new_name] = profiles.pop(old_name)

        if self._data.get("active_profile") == old_name:
            self._data["active_profile"] = new_name

        schedule = self._data.get("weekly_schedule", {}) or {}
        for key in self.WEEKDAY_KEYS:
            if schedule.get(key) == old_name:
                schedule[key] = new_name
        self._data["weekly_schedule"] = schedule

        self._save_raw(self._data)

    def delete_profile(self, name: str) -> None:
        profiles = self._data.setdefault("profiles", {})
        if name not in profiles:
            return
        if len(profiles) == 1:
            raise ValueError("Cannot delete the only existing profile")

        profiles.pop(name)

        if self._data.get("active_profile") == name:
            self._data["active_profile"] = next(iter(profiles.keys()))

        schedule = self._data.get("weekly_schedule", {}) or {}
        for key in self.WEEKDAY_KEYS:
            if schedule.get(key) == name:
                schedule[key] = self._data["active_profile"]
        self._data["weekly_schedule"] = schedule

        self._save_raw(self._data)


    def get_weekly_schedule(self) -> Dict[str, str]:

        schedule = self._data.get("weekly_schedule", {}) or {}
        profiles = self._data.get("profiles", {}) or {}

        # нормалізуємо, щоб кожний день мав валідний профіль
        active = self.get_active_profile_name()
        for key in self.WEEKDAY_KEYS:
            prof = schedule.get(key, active)
            if prof not in profiles:
                prof = active
            schedule[key] = prof

        self._data["weekly_schedule"] = schedule
        self._save_raw(self._data)
        return schedule

    def save_weekly_schedule(self, schedule: Dict[str, str]) -> None:
        profiles = self._data.get("profiles", {}) or {}
        active = self.get_active_profile_name()

        normalized: Dict[str, str] = {}
        for idx, key in enumerate(self.WEEKDAY_KEYS):
            prof = schedule.get(key)
            if prof not in profiles:
                prof = active
            normalized[key] = prof

        self._data["weekly_schedule"] = normalized
        self._save_raw(self._data)
