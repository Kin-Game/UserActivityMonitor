from typing import Dict
from datetime import datetime, date, timedelta, time as dtime

from storage.sqlite_repo import SQLiteSessionRepository


class AnalyticsService:

    def __init__(self):
        self.repo = SQLiteSessionRepository()

    def get_today_category_minutes(self) -> Dict[str, float]:

        totals_sec = self.repo.get_today_category_totals()
        totals_min: Dict[str, float] = {}
        for cat, sec in totals_sec.items():
            if sec <= 0:
                continue
            totals_min[cat] = round(sec / 60.0, 1)
        return totals_min

    def get_today_activity_vs_breaks(self) -> Dict[str, int]:

        # Активність: сумарний час усіх не-idle сесій за сьогодні
        totals_sec = self.repo.get_today_category_totals()
        active_sec = int(sum(sec for sec in totals_sec.values() if sec > 0))

        # Перерви: всі перерви з таблиці breaks за сьогодні
        today: date = datetime.now().date()
        start_dt = datetime.combine(today, dtime.min)
        end_dt = datetime.combine(today + timedelta(days=1), dtime.min)
        start_ts = int(start_dt.timestamp())
        end_ts = int(end_dt.timestamp())

        summary = self.repo.get_breaks_summary_for_range(start_ts, end_ts)
        break_sec = int(summary.get("total_duration_sec", 0) or 0)

        return {
            "active_sec": max(active_sec, 0),
            "break_sec": max(break_sec, 0),
        }
