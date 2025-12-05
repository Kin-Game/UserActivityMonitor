import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from config.settings import DB_PATH


class SQLiteSessionRepository:

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or DB_PATH
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._init_db()

    # ---------- Внутрішні методи ----------

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            cur = conn.cursor()

            # --- sessions ---
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    day TEXT NOT NULL,
                    start TEXT NOT NULL,
                    end TEXT NOT NULL,
                    duration_sec INTEGER NOT NULL,
                    app TEXT NOT NULL,
                    title TEXT,
                    category TEXT,
                    is_idle INTEGER NOT NULL DEFAULT 0
                )
                """
            )

            # Міграція 01: якщо старе поле is_idle не існує
            try:
                cur.execute("SELECT is_idle FROM sessions LIMIT 1")
            except sqlite3.OperationalError:
                cur.execute("ALTER TABLE sessions ADD COLUMN is_idle INTEGER NOT NULL DEFAULT 0")

            # --- breaks (НОВА ТАБЛИЦЯ) ---
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS breaks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_ts INTEGER NOT NULL,
                    end_ts INTEGER NOT NULL,
                    duration_sec INTEGER NOT NULL,
                    last_category TEXT
                )
                """
            )

            conn.commit()

    # ---------- Збереження звичайних сесій ----------

    def save_session(self, session: dict) -> None:
        start = session.get("start")
        end = session.get("end")
        duration_sec = int(session.get("duration_sec") or 0)
        app = session.get("app") or ""
        title = session.get("title") or ""
        category = session.get("category") or ""
        is_idle = 1 if session.get("idle") else 0

        day = ""
        if start:
            try:
                day = datetime.fromisoformat(start).strftime("%Y-%m-%d")
            except Exception:
                day = start[:10]

        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO sessions (day, start, end, duration_sec, app, title, category, is_idle)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (day, start, end, duration_sec, app, title, category, is_idle),
            )
            conn.commit()

    # ---------- AGG: Категорії за сьогодні ----------

    def get_today_category_totals(self) -> Dict[str, int]:
        today = datetime.now().strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT category, SUM(duration_sec)
                FROM sessions
                WHERE day = ? AND is_idle = 0
                GROUP BY category
                """,
                (today,),
            )
            rows = cur.fetchall()

        totals: Dict[str, int] = {}
        for cat, total in rows:
            cat = cat or "other"
            totals[cat] = int(total or 0)
        return totals

    # ---------- Трендові діаграми ----------

    def get_daily_totals(self, start_day: str, end_day: str) -> Dict[str, float]:

        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT day, SUM(duration_sec)/60.0 AS minutes
                FROM sessions
                WHERE day >= ? AND day <= ? AND is_idle = 0
                GROUP BY day
                ORDER BY day
                """,
                (start_day, end_day),
            )
            rows = cur.fetchall()

        return {r["day"]: (r["minutes"] or 0.0) for r in rows}

    def get_daily_totals_by_category(self, start_day: str, end_day: str, category: str) -> Dict[str, float]:

        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT day, SUM(duration_sec)/60.0 AS minutes
                FROM sessions
                WHERE day >= ? AND day <= ? AND category = ? AND is_idle = 0
                GROUP BY day
                ORDER BY day
                """,
                (start_day, end_day, category),
            )
            rows = cur.fetchall()

        return {r["day"]: (r["minutes"] or 0.0) for r in rows}

    def get_daily_totals_by_app(self, start_day: str, end_day: str, app: str) -> Dict[str, float]:

        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT day, SUM(duration_sec)/60.0 AS minutes
                FROM sessions
                WHERE day >= ? AND day <= ? AND app = ? AND is_idle = 0
                GROUP BY day
                ORDER BY day
                """,
                (start_day, end_day, app),
            )
            rows = cur.fetchall()

        return {r["day"]: (r["minutes"] or 0.0) for r in rows}

    def get_hourly_heatmap(self, start_day: str, end_day: str) -> Dict[str, Dict[int, float]]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT day,
                       strftime('%H', start) AS hour,
                       SUM(duration_sec)/60.0 AS minutes
                FROM sessions
                WHERE day >= ? AND day <= ? AND is_idle = 0
                GROUP BY day, hour
                ORDER BY day, hour
                """,
                (start_day, end_day),
            )
            rows = cur.fetchall()

        result: Dict[str, Dict[int, float]] = {}
        for r in rows:
            day = r["day"]
            hour_str = r["hour"]
            if hour_str is None:
                continue
            try:
                h = int(hour_str)
            except ValueError:
                continue
            minutes = float(r["minutes"] or 0.0)
            if day not in result:
                result[day] = {}
            result[day][h] = minutes

        return result

    # =======================================================
    # ================       BREAKS API      ================
    # =======================================================

    def save_break(
        self,
        start_ts: int,
        end_ts: int,
        last_category: Optional[str] = None
    ) -> int:
        """Зберігає одну перерву."""
        duration_sec = max(0, end_ts - start_ts)
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO breaks (start_ts, end_ts, duration_sec, last_category)
                VALUES (?, ?, ?, ?)
                """,
                (start_ts, end_ts, duration_sec, last_category),
            )
            conn.commit()
            return cur.lastrowid

    def get_breaks_for_range(self, start_ts: int, end_ts: int) -> List[Dict]:
        """Повертає всі перерви у діапазоні timestamp."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, start_ts, end_ts, duration_sec, last_category
                FROM breaks
                WHERE start_ts >= ? AND start_ts < ?
                ORDER BY start_ts ASC
                """,
                (start_ts, end_ts),
            )
            rows = cur.fetchall()

        return [
            {
                "id": r["id"],
                "start_ts": r["start_ts"],
                "end_ts": r["end_ts"],
                "duration_sec": r["duration_sec"],
                "last_category": r["last_category"],
            }
            for r in rows
        ]

    def get_breaks_summary_for_range(self, start_ts: int, end_ts: int) -> Dict:
        """Агрегація перерв: кількість + загальна тривалість."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(duration_sec), 0)
                FROM breaks
                WHERE start_ts >= ? AND start_ts < ?
                """,
                (start_ts, end_ts),
            )
            count, total = cur.fetchone()

        return {
            "count": int(count or 0),
            "total_duration_sec": int(total or 0),
        }
