import time
from typing import Dict, Optional, Tuple

from core.analytics import AnalyticsService
from storage.limits_repo import CategoryLimitsRepository, CATEGORIES


class RuleEngine:

    COOLDOWN_WARNING = 20 * 60   # 20 хв для post-toast
    COOLDOWN_OVER = 5 * 60       # 5 хв для post-toast

    def __init__(self):
        self.analytics = AnalyticsService()
        self.limits_repo = CategoryLimitsRepository()

        # для post-toast (після завершення сесії): category -> timestamp
        self.last_notified: Dict[str, float] = {}

        # для live-toast: category -> last_level ("none" / "warning" / "over")
        self.live_state: Dict[str, str] = {}

        self.human_names = {
            "work": "робота",
            "games": "ігри",
            "media": "медіа",
            "browsing": "серфінг",
            "communication": "спілкування",
            "social": "соцмережі",
            "education": "навчання",
            "other": "інше",
        }

    # ---------- утиліти ----------

    def _build_message(
        self, category: str, used_min: float, limit_min: float, level: str
    ) -> str:
        name = self.human_names.get(category, category)
        used_round = round(used_min)
        text = (
            f"{name.capitalize()} "
            f"{'перевищує' if level == 'over' else 'наближається до'} ліміту: "
            f"{used_round}/{int(limit_min)} хв. "
        )
        if level == "over":
            text += "Рекомендуємо зробити перерву."
        else:
            text += "Варто спланувати короткий відпочинок."
        return text

    def _should_notify_post(self, category: str, level: str) -> bool:
        """
        Антиспам тільки для post-toast (check_overall).
        """
        now = time.time()
        cooldown = self.COOLDOWN_OVER if level == "over" else self.COOLDOWN_WARNING
        last = self.last_notified.get(category, 0.0)
        if now - last < cooldown:
            return False
        self.last_notified[category] = now
        return True

    # ---------- LIVE-ПЕРЕВІРКА ДЛЯ ПОТОЧНОЇ СЕСІЇ ----------

    def check_live_category(
        self,
        category: str,
        current_session_sec: int,
    ) -> Optional[Tuple[str, str]]:

        if category not in CATEGORIES or current_session_sec <= 0:
            return None

        limits = self.limits_repo.get_all_limits()
        cfg = limits.get(category)
        if not cfg or not cfg["enabled"]:
            return None

        limit_min = cfg["limit_minutes"]
        if limit_min <= 0:
            return None

        used_today = self.analytics.get_today_category_minutes().get(category, 0.0)
        extra_min = current_session_sec / 60.0
        used_total = used_today + extra_min

        ratio = used_total / limit_min

        if ratio >= 1.0:
            level = "over"
        elif ratio >= 0.8:
            level = "warning"
        else:
            level = "none"

        prev_level = self.live_state.get(category, "none")
        self.live_state[category] = level

        # Тост показуємо лише в момент ПЕРЕХОДУ рівня
        if level == "warning" and prev_level == "none":
            msg = self._build_message(category, used_total, limit_min, "warning")
            return msg, "warning"

        if level == "over" and prev_level != "over":
            # можемо перейти як з none, так і з warning
            msg = self._build_message(category, used_total, limit_min, "over")
            return msg, "over"

        return None

    # ---------- ПЕРЕВІРКА ПІСЛЯ ЗАВЕРШЕННЯ СЕСІЇ ----------

    def check_overall(self) -> Optional[Tuple[str, str]]:

        used = self.analytics.get_today_category_minutes()
        limits = self.limits_repo.get_all_limits()

        best: Optional[Tuple[str, str, float, float, float]] = None
        # (category, level, ratio, used_min, limit_min)

        for cat in CATEGORIES:
            cfg = limits.get(cat)
            if not cfg or not cfg["enabled"]:
                continue

            limit_min = cfg["limit_minutes"]
            if limit_min <= 0:
                continue

            used_min = used.get(cat, 0.0)
            if used_min <= 0:
                continue

            ratio = used_min / limit_min
            if ratio >= 1.0:
                level = "over"
            elif ratio >= 0.8:
                level = "warning"
            else:
                continue

            if not self._should_notify_post(cat, level):
                continue

            if best is None:
                best = (cat, level, ratio, used_min, limit_min)
            else:
                _, lvl_b, r_b, _, _ = best
                sev_best = 1 if lvl_b == "over" else 0
                sev_new = 1 if level == "over" else 0
                if (sev_new, ratio) > (sev_best, r_b):
                    best = (cat, level, ratio, used_min, limit_min)

        if best is None:
            return None

        cat, level, _, used_min, limit_min = best
        msg = self._build_message(cat, used_min, limit_min, level)
        return msg, level
