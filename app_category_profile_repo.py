from __future__ import annotations
from pathlib import Path
import json
from typing import List, Dict, Optional, Any


class AppCategoryProfileRepository:


    def __init__(self, path: Optional[Path] = None):
        if path is None:
            base = Path("data")
            base.mkdir(exist_ok=True)
            path = base / "app_categories.json"
        self.path = path

    # ---- внутрішні допоміжні ----

    def _load_raw(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"rules": []}
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return {"rules": []}
        if not isinstance(data, dict):
            return {"rules": []}
        data.setdefault("rules", [])
        return data

    def _save_raw(self, data: Dict[str, Any]) -> None:
        data = dict(data or {})
        data.setdefault("rules", [])
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ---- публічні методи ----

    def get_rules(self) -> List[Dict[str, str]]:
        data = self._load_raw()
        rules = data.get("rules", [])
        if not isinstance(rules, list):
            return []
        # легка нормалізація
        norm: List[Dict[str, str]] = []
        for r in rules:
            if not isinstance(r, dict):
                continue
            exe = str(r.get("exe", "")).strip()
            title_contains = str(r.get("title_contains", "")).strip()
            category = str(r.get("category", "")).strip()
            if exe and category:
                norm.append(
                    {
                        "exe": exe,
                        "title_contains": title_contains,
                        "category": category,
                    }
                )
        return norm

    def set_rules(self, rules: List[Dict[str, str]]) -> None:
 
        cleaned: List[Dict[str, str]] = []
        for r in rules:
            exe = str(r.get("exe", "")).strip()
            title_contains = str(r.get("title_contains", "")).strip()
            category = str(r.get("category", "")).strip()
            if exe and category:
                cleaned.append(
                    {
                        "exe": exe,
                        "title_contains": title_contains,
                        "category": category,
                    }
                )
        self._save_raw({"rules": cleaned})

    def find_match(self, exe: str, title: str) -> Optional[str]:

        exe = (exe or "").strip()
        title_low = (title or "").lower()

        for r in self.get_rules():
            if r.get("exe") != exe:
                continue
            pattern = (r.get("title_contains") or "").lower()
            if pattern and pattern not in title_low:
                continue
            return r.get("category")
        return None
