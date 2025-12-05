import os
import json
from typing import Tuple, Dict


class CategoryProfileRepository:


    def __init__(self, path: str = "storage/category_profiles.json"):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._cache: Dict[str, dict] | None = None

    # -------- Внутрішні методи --------

    def _load(self) -> Dict[str, dict]:
        if self._cache is not None:
            return self._cache
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
        except FileNotFoundError:
            self._cache = {}
        return self._cache

    def _save(self) -> None:
        if self._cache is None:
            return
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)

    # -------- Публічний інтерфейс --------

    def get_stats(self, signature: str) -> Tuple[Dict[str, int], int]:
 
        data = self._load().get(signature, {})
        counts: Dict[str, int] = data.get("counts", {})
        total = sum(counts.values())
        return counts, total

    def get_majority(self, signature: str) -> Tuple[str | None, int, float]:

        counts, total = self.get_stats(signature)
        if not counts or total == 0:
            return None, 0, 0.0

        cat, cnt = max(counts.items(), key=lambda kv: kv[1])
        share = cnt / total if total > 0 else 0.0
        return cat, cnt, share

    def increment(self, signature: str, category: str) -> None:

        data = self._load()
        if signature not in data:
            data[signature] = {"counts": {}}
        counts: Dict[str, int] = data[signature]["counts"]
        counts[category] = counts.get(category, 0) + 1
        self._save()
