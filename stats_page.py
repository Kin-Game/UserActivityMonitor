import html
from datetime import date, timedelta, datetime, time as dtime
from pathlib import Path
import sqlite3

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QDateEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QGroupBox,
    QHeaderView,
    QSplitter,
    QTextEdit,
    QSizePolicy,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from config.settings import DB_PATH
from core.utils import format_duration_human
from core.period_analysis import PeriodAnalysisService
from ui.components.category_chart import CATEGORY_LABELS, CATEGORY_COLORS
from storage.sqlite_repo import SQLiteSessionRepository
from storage.settings_repo import SettingsRepository
from core.settings_service import SettingsService


class StatsPage(QWidget):
    """
    Розширена аналітика: категорії, перерви, топ застосунків, трендовий графік, теплова карта, AI-звіт.
    """

    def __init__(self, db_path: str | Path | None = None, parent=None):
        super().__init__(parent)

        self.db_path = Path(db_path or DB_PATH)
        self.repo = SQLiteSessionRepository(str(self.db_path))
        self.period_ai_service = PeriodAnalysisService()

        # сервіс налаштувань (для break_min_visible_sec та ін.)
        self._settings_repo = SettingsRepository(DB_PATH)
        self._settings = SettingsService(self._settings_repo)

        self._last_daily_totals_all: dict[str, float] = {}
        self._last_period: tuple[str, str] | None = None
        self._hourly_heatmap_data: dict[str, dict[int, float]] = {}
        self._cached_cat_minutes: dict[str, float] = {}
        self._cached_apps: list[tuple[str, str, str, float]] = []

        # ----------------- ROOT -----------------
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # ----------------- FILTERS -----------------
        filters_box = QGroupBox("Фільтр періоду")
        filters_layout = QHBoxLayout(filters_box)

        self.range_combo = QComboBox()
        self.range_combo.addItems(
            [
                "Сьогодні",
                "Вчора",
                "Останні 7 днів",
                "Останні 30 днів",
                "Увесь час",
                "Власний інтервал",
            ]
        )
        self.range_combo.currentIndexChanged.connect(self._on_range_change)

        self.from_date = QDateEdit()
        self.from_date.setDisplayFormat("dd.MM.yyyy")
        self.from_date.setCalendarPopup(True)

        self.to_date = QDateEdit()
        self.to_date.setDisplayFormat("dd.MM.yyyy")
        self.to_date.setCalendarPopup(True)

        self.btn_apply = QPushButton("Оновити")
        self.btn_apply.clicked.connect(self.refresh)

        filters_layout.addWidget(QLabel("Період:"))
        filters_layout.addWidget(self.range_combo)
        filters_layout.addSpacing(12)
        filters_layout.addWidget(QLabel("З:"))
        filters_layout.addWidget(self.from_date)
        filters_layout.addWidget(QLabel("По:"))
        filters_layout.addWidget(self.to_date)
        filters_layout.addStretch()
        filters_layout.addWidget(self.btn_apply)

        self._init_dates_defaults()

        # ----------------- ЧАС ЗА КАТЕГОРІЯМИ ТА ПЕРЕРВИ (верхній блок зліва) ---------
        chart_group = QGroupBox("Час за категоріями та перерви")
        chart_group.setMinimumHeight(285)
        chart_group.setMaximumHeight(285) 

        chart_layout = QHBoxLayout(chart_group)
        chart_layout.setContentsMargins(8, 8, 8, 8)
        chart_layout.setSpacing(16)

        # PIE CHART (з легендою всередині самої фігури)
        self.pie_fig = Figure(facecolor="none")
        self.pie_canvas = FigureCanvas(self.pie_fig)
        self.pie_canvas.setMinimumHeight(240)
        self.pie_canvas.setMaximumHeight(240)
        self.pie_canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # BALANCE BAR (праворуч)
        self.breaks_balance_fig = Figure(facecolor="none")
        self.breaks_balance_canvas = FigureCanvas(self.breaks_balance_fig)
        self.breaks_balance_canvas.setMinimumHeight(210)
        self.breaks_balance_canvas.setMaximumHeight(210)
        self.breaks_balance_canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        chart_layout.addWidget(self.pie_canvas, 5)
        chart_layout.addWidget(self.breaks_balance_canvas, 3)

        # ----------------- BREAKS TABLE (під пай-чартом) -------
        breaks_group = QGroupBox("Перерви за період")
        breaks_layout = QVBoxLayout(breaks_group)

        self.breaks_summary_label = QLabel("Перерви: —")
        breaks_layout.addWidget(self.breaks_summary_label)

        self.breaks_table = QTableWidget(0, 4)
        self.breaks_table.setHorizontalHeaderLabels(
            ["Початок", "Кінець", "Тривалість", "Категорія перед перервою"]
        )
        bh = self.breaks_table.horizontalHeader()
        bh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        bh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        bh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        bh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.breaks_table.setMinimumHeight(120)
        breaks_layout.addWidget(self.breaks_table)

        # ----------------- TOP APPS TABLE -----------------------
        apps_group = QGroupBox("Топ застосунків за часом використання")
        apps_layout = QVBoxLayout(apps_group)

        self.table_apps = QTableWidget(0, 4)
        self.table_apps.setHorizontalHeaderLabels(
            ["Застосунок", "Вікно / заголовок", "Категорія", "Час"]
        )
        header = self.table_apps.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_apps.cellClicked.connect(self._on_app_row_clicked)
        apps_layout.addWidget(self.table_apps)

        # ----------------- TREND CHART (праворуч згори) ---------
        trend_group = QGroupBox("Динаміка активності по днях")
        trend_layout = QVBoxLayout(trend_group)

        trend_controls = QHBoxLayout()
        trend_mode_label = QLabel("Режим графіка:")
        self.trend_mode_combo = QComboBox()
        self.trend_mode_combo.addItem("Усі категорії", userData="all")
        self.trend_mode_combo.addItem("Окрема категорія", userData="category")
        self.trend_mode_combo.addItem("Окремий застосунок", userData="app")
        self.trend_mode_combo.currentIndexChanged.connect(self._on_trend_mode_changed)

        trend_category_label = QLabel("Категорія:")
        self.trend_category_combo = QComboBox()
        self.trend_category_combo.addItem("Всі категорії", userData=None)
        for key, lbl in sorted(CATEGORY_LABELS.items(), key=lambda x: x[1]):
            self.trend_category_combo.addItem(lbl, userData=key)
        self.trend_category_combo.currentIndexChanged.connect(
            self._on_trend_category_changed
        )
        self.trend_category_combo.setEnabled(False)

        trend_app_label = QLabel("Застосунок:")
        self.trend_app_combo = QComboBox()
        self.trend_app_combo.addItem("Всі застосунки", userData=None)
        self.trend_app_combo.currentIndexChanged.connect(self._on_trend_app_changed)
        self.trend_app_combo.setEnabled(False)

        trend_controls.addWidget(trend_mode_label)
        trend_controls.addWidget(self.trend_mode_combo)
        trend_controls.addSpacing(12)
        trend_controls.addWidget(trend_category_label)
        trend_controls.addWidget(self.trend_category_combo)
        trend_controls.addSpacing(12)
        trend_controls.addWidget(trend_app_label)
        trend_controls.addWidget(self.trend_app_combo)
        trend_controls.addStretch()

        trend_layout.addLayout(trend_controls)

        self.trend_fig = Figure(facecolor="none")
        self.trend_canvas = FigureCanvas(self.trend_fig)
        self.trend_canvas.setMinimumHeight(250)
        self.trend_canvas.setMaximumHeight(250)
        trend_layout.addWidget(self.trend_canvas)

        # ----------------- HEATMAP (праворуч по центру) ---------
        heatmap_group = QGroupBox("Теплова карта активності (година × день)")
        heatmap_layout = QVBoxLayout(heatmap_group)

        self.heatmap_fig = Figure(facecolor="none")
        self.heatmap_canvas = FigureCanvas(self.heatmap_fig)
        self.heatmap_canvas.setMinimumHeight(240)
        self.heatmap_canvas.setMaximumHeight(240)
        heatmap_layout.addWidget(self.heatmap_canvas)

        # ----------------- AI REPORT (праворуч знизу) -----------
        ai_group = QGroupBox("AI-звіт за період")
        ai_layout = QVBoxLayout(ai_group)

        self.btn_ai_report = QPushButton("Згенерувати AI-звіт")
        self.btn_ai_report.clicked.connect(self._on_ai_report)

        self.ai_output = QTextEdit()
        self.ai_output.setReadOnly(True)
        self.ai_output.setPlaceholderText("Тут з'явиться AI-аналітика за період...")
        ai_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ai_output.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ai_output.setMinimumHeight(260)

        ai_layout.addWidget(self.btn_ai_report)
        ai_layout.addWidget(self.ai_output)

        # ----------------- LEFT COLUMN CONTAINER ----------------
        left_container = QWidget()
        left_col = QVBoxLayout(left_container)
        left_col.setSpacing(16)
        left_col.addWidget(filters_box)
        left_col.addWidget(chart_group)
        left_col.addWidget(breaks_group)
        left_col.addWidget(apps_group)

        # ----------------- RIGHT COLUMN CONTAINER ---------------
        right_container = QWidget()
        right_col = QVBoxLayout(right_container)
        right_col.setSpacing(16)
        right_col.addWidget(trend_group)
        right_col.addWidget(heatmap_group)
        right_col.addWidget(ai_group)
        right_col.addStretch()

        # ----------------- SPLITTER 50/50 -----------------------
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_container)
        splitter.addWidget(right_container)

        # співвідношення при ресайзі
        splitter.setStretchFactor(0, 3)   
        splitter.setStretchFactor(1, 2)  

        self._splitter = splitter
        root.addWidget(splitter)

        self.refresh()


    def showEvent(self, event):
        super().showEvent(event)

        total = self.width()
        if total <= 0:
            return

        left = int(total * 0.75)
        right = total - left
        self._splitter.setSizes([left, right])


    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "_splitter"):
            return
        total_width = self._splitter.size().width()
        half = int(total_width / 2)
        self._splitter.setSizes([half, half])

    # ----------------- HELPERS ---------------------------------
    def _init_dates_defaults(self):
        today = date.today()
        self.to_date.setDate(QDate(today.year, today.month, today.day))
        self.from_date.setDate(QDate(today.year, today.month, today.day))

    def _on_range_change(self, index: int):
        today = date.today()
        choice = self.range_combo.currentText()

        if choice == "Сьогодні":
            start = today
            end = today
        elif choice == "Вчора":
            start = today - timedelta(days=1)
            end = today - timedelta(days=1)
        elif choice == "Останні 7 днів":
            end = today
            start = today - timedelta(days=6)
        elif choice == "Останні 30 днів":
            end = today
            start = today - timedelta(days=29)
        elif choice == "Увесь час":
            end = today
            start = today - timedelta(days=365 * 10)
        else:
            return

        self.from_date.setDate(QDate(start.year, start.month, start.day))
        self.to_date.setDate(QDate(end.year, end.month, end.day))

    def refresh(self):
        start_day, end_day = self._get_selected_days()
        cat_minutes, apps = self._query_categories(start_day, end_day)

        start_str = start_day.strftime("%Y-%m-%d")
        end_str = end_day.strftime("%Y-%m-%d")
        self._last_period = (start_str, end_str)
        self._last_daily_totals_all = self.repo.get_daily_totals(start_str, end_str)
        self._hourly_heatmap_data = self.repo.get_hourly_heatmap(start_str, end_str)

        self._cached_cat_minutes = cat_minutes
        self._cached_apps = apps

        self._update_pie(cat_minutes)
        self._update_breaks_table(start_day, end_day)
        self._update_breaks_balance_bar(start_day, end_day)
        self._update_apps_table(apps)
        self._update_trend_app_combo(apps)
        self._update_trend_for_current_mode()
        self._update_heatmap(self._hourly_heatmap_data)

    def _get_selected_days(self) -> tuple[date, date]:
        d1 = self.from_date.date()
        d2 = self.to_date.date()
        return (
            date(d1.year(), d1.month(), d1.day()),
            date(d2.year(), d2.month(), d2.day()),
        )

    def _query_categories(self, start_day: date, end_day: date):
        start = start_day.strftime("%Y-%m-%d")
        end = end_day.strftime("%Y-%m-%d")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute(
            """
            SELECT category, SUM(duration_sec) AS total_sec
            FROM sessions
            WHERE day >= ? AND day <= ?
            GROUP BY category
            """,
            (start, end),
        )
        rows_cat = cur.fetchall()
        cat_minutes = {
            (r["category"] or "other"): (r["total_sec"] or 0) / 60.0 for r in rows_cat
        }

        cur.execute(
            """
            SELECT app, title, category, SUM(duration_sec) AS total_sec
            FROM sessions
            WHERE day >= ? AND day <= ?
            GROUP BY app, title, category
            ORDER BY total_sec DESC
            LIMIT 50
            """,
            (start, end),
        )
        rows_apps = cur.fetchall()
        apps = [
            (
                r["app"],
                r["title"],
                r["category"] or "other",
                (r["total_sec"] or 0) / 60.0,
            )
            for r in rows_apps
        ]

        conn.close()
        return cat_minutes, apps

    # ----------------- BREAKS TABLE ----------------------------
    def _get_break_min_visible_sec(self) -> int:
        cfg = self._settings_repo.all()
        try:
            val = int(cfg.get("break_min_visible_sec", 5) or 0)
        except (TypeError, ValueError):
            val = 5
        return max(val, 0)

    def _update_breaks_table(self, start_day: date, end_day: date):
        day_start_dt = datetime.combine(start_day, dtime.min)
        day_end_dt = datetime.combine(end_day + timedelta(days=1), dtime.min)

        start_ts = int(day_start_dt.timestamp())
        end_ts = int(day_end_dt.timestamp())

        breaks = self.repo.get_breaks_for_range(start_ts, end_ts)
        summary = self.repo.get_breaks_summary_for_range(start_ts, end_ts)

        min_visible_sec = self._get_break_min_visible_sec()

        micro_breaks = []
        visible_breaks = []

        for br in breaks:
            if br["duration_sec"] < min_visible_sec:
                micro_breaks.append(br)
            else:
                visible_breaks.append(br)

        total_sec = summary.get("total_duration_sec", 0)
        count = summary.get("count", 0)
        total_str = format_duration_human(int(total_sec))

        if count == 0:
            self.breaks_summary_label.setText("Перерви: немає записів за обраний період.")
        else:
            self.breaks_summary_label.setText(
                f"Перерви: {count} шт, сумарно {total_str}."
            )

        rows = len(visible_breaks) + (1 if micro_breaks else 0)
        self.breaks_table.setRowCount(rows)
        row_idx = 0

        if micro_breaks:
            total_micro_sec = sum(br["duration_sec"] for br in micro_breaks)
            total_micro_str = format_duration_human(total_micro_sec)

            self.breaks_table.setItem(row_idx, 0, QTableWidgetItem("— дрібні перерви —"))
            self.breaks_table.setItem(row_idx, 1, QTableWidgetItem("—"))
            self.breaks_table.setItem(row_idx, 2, QTableWidgetItem(total_micro_str))

            cats = [br.get("last_category") for br in micro_breaks if br.get("last_category")]
            if cats:
                from collections import Counter
                most_common = Counter(cats).most_common(1)[0][0]
            else:
                most_common = "—"

            label = CATEGORY_LABELS.get(most_common, most_common)
            self.breaks_table.setItem(row_idx, 3, QTableWidgetItem(label))

            row_idx += 1

        for br in visible_breaks:
            start_dt = datetime.fromtimestamp(br["start_ts"])
            end_dt = datetime.fromtimestamp(br["end_ts"])

            duration_str = format_duration_human(br["duration_sec"])
            last_cat = br.get("last_category") or "—"
            last_cat_label = CATEGORY_LABELS.get(last_cat, last_cat)

            self.breaks_table.setItem(
                row_idx,
                0,
                QTableWidgetItem(start_dt.strftime("%Y-%m-%d %H:%M:%S")),
            )
            self.breaks_table.setItem(
                row_idx,
                1,
                QTableWidgetItem(end_dt.strftime("%Y-%m-%d %H:%M:%S")),
            )
            self.breaks_table.setItem(row_idx, 2, QTableWidgetItem(duration_str))
            self.breaks_table.setItem(row_idx, 3, QTableWidgetItem(last_cat_label))

            row_idx += 1

        self.breaks_table.resizeRowsToContents()


    def _update_breaks_balance_bar(self, start_day: date, end_day: date):


        self.breaks_balance_fig.clear()
        ax = self.breaks_balance_fig.add_subplot(111)
        ax.set_facecolor("#202020")
        self.breaks_balance_fig.patch.set_facecolor("#202020")

        # Обчислення періоду
        day_start_dt = datetime.combine(start_day, dtime.min)
        day_end_dt = datetime.combine(end_day + timedelta(days=1), dtime.min)
        start_ts = int(day_start_dt.timestamp())
        end_ts = int(day_end_dt.timestamp())

        # Дані по перервах
        summary = self.repo.get_breaks_summary_for_range(start_ts, end_ts)
        break_sec = int(summary.get("total_duration_sec", 0) or 0)

        # Дані по активності (з daily_totals)
        if not self._last_daily_totals_all:
            start_str = start_day.strftime("%Y-%m-%d")
            end_str = end_day.strftime("%Y-%m-%d")
            self._last_daily_totals_all = self.repo.get_daily_totals(start_str, end_str)

        active_min = sum(self._last_daily_totals_all.values())
        active_sec = int(active_min * 60)

        total = active_sec + break_sec
        if total <= 0:
            ax.text(0.5, 0.5, "Немає даних", ha="center", va="center", color="white")
            ax.axis("off")
            self.breaks_balance_canvas.draw()
            return

        active_pct = active_sec / total
        break_pct = break_sec / total

        # Формат часу для підпису
        def fmt(sec: int) -> str:
            if sec < 60:
                return f"{sec} с"
            m = sec // 60
            h = m // 60
            m = m % 60
            if h > 0:
                return f"{h} год {m} хв"
            return f"{m} хв"

        active_str = fmt(active_sec)
        break_str = fmt(break_sec)

        # Y-позиції (дві тонкі смуги)
        y_pos = [0.7, 0.2]
        bar_height = 0.18  # тонші смуги

        # --- Активність ---
        ax.barh(y_pos[0], active_pct, height=bar_height, color="#4CAF50")
        text_x = active_pct - 0.02 if active_pct > 0.15 else active_pct + 0.02
        ha = "right" if active_pct > 0.15 else "left"
        ax.text(
            text_x,
            y_pos[0],
            f"Активність — {active_pct * 100:.0f}%",
            va="center",
            ha=ha,
            color="white",
            fontsize=9,
        )

        # --- Перерви ---
        ax.barh(y_pos[1], break_pct, height=bar_height, color="#B0BEC5")
        text_x2 = break_pct - 0.02 if break_pct > 0.15 else break_pct + 0.02
        ha2 = "right" if break_pct > 0.15 else "left"
        ax.text(
            text_x2,
            y_pos[1],
            f"Перерви — {break_pct * 100:.0f}%",
            va="center",
            ha=ha2,
            color="white",
            fontsize=9,
        )

        # Оформлення осей і сітки (все біле)
        ax.set_yticks([])
        ax.set_xlim(0, 1)
        ax.set_xlabel("")
        ax.set_title("Баланс активність / перерви", color="white", pad=8)

        ax.grid(True, axis="x", linestyle="--", alpha=0.25, color="#AAAAAA")
        ax.tick_params(axis="x", colors="white")
        for spine in ax.spines.values():
            spine.set_color("#404040")

        # Підпис під графіком
        caption = (
            f"За період: {active_str} активності, {break_str} перерв "
            f"({break_pct*100:.0f}%)."
        )

        ax.text(
            0.5,
            -0.32,    
            caption,
            ha="center",
            va="center",
            color="white",
            fontsize=9,
        )

        self.breaks_balance_fig.subplots_adjust(
            left=0.10, right=0.95, top=0.80, bottom=0.32
        )

        self.breaks_balance_canvas.draw()

    # ----------------- BREAKS CHART -----------------------------
    def _update_breaks_chart(self, start_day: date, end_day: date):
        self.breaks_fig_chart.clear()
        ax = self.breaks_fig_chart.add_subplot(111)
        ax.set_facecolor("#202020")
        self.breaks_fig_chart.patch.set_facecolor("#202020")

        day_start_dt = datetime.combine(start_day, dtime.min)
        day_end_dt = datetime.combine(end_day + timedelta(days=1), dtime.min)
        start_ts = int(day_start_dt.timestamp())
        end_ts = int(day_end_dt.timestamp())

        breaks = self.repo.get_breaks_for_range(start_ts, end_ts)

        if not breaks:
            ax.text(
                0.5,
                0.5,
                "Немає перерв за обраний період",
                color="white",
                ha="center",
                va="center",
            )
            ax.axis("off")
            self.breaks_canvas_chart.draw()
            return

        # агрегуємо по годинах доби
        hour_to_min = {h: 0.0 for h in range(24)}
        for br in breaks:
            start_dt = datetime.fromtimestamp(br["start_ts"])
            h = start_dt.hour
            hour_to_min[h] += (br["duration_sec"] or 0) / 60.0

        hours = [h for h, val in hour_to_min.items() if val > 0]
        if not hours:
            ax.text(
                0.5,
                0.5,
                "Немає значущих перерв",
                color="white",
                ha="center",
                va="center",
            )
            ax.axis("off")
            self.breaks_canvas_chart.draw()
            return

        hours.sort()
        values = [hour_to_min[h] for h in hours]

        x_idx = list(range(len(hours)))
        labels = [f"{h:02d}:00" for h in hours]

        def _ytick_fmt(v, pos):
            seconds = int(round(v * 60))
            if seconds <= 0:
                return "0"
            return format_duration_human(seconds)

        ax.yaxis.set_major_formatter(FuncFormatter(_ytick_fmt))

        bar_color = CATEGORY_COLORS.get("other", "#4FC3F7")
        ax.bar(x_idx, values, width=0.6, color=bar_color)

        ax.set_xticks(x_idx)
        ax.set_xticklabels(labels, rotation=0, ha="center", color="white")

        ax.set_ylabel("Час у перервах", color="white")
        ax.set_title("Перерви по годинах (сума за період)", color="white")

        ax.grid(True, linestyle="--", alpha=0.3, color="#AAAAAA")
        ax.tick_params(axis="y", colors="white")
        ax.spines["bottom"].set_color("white")
        ax.spines["left"].set_color("white")
        ax.spines["top"].set_color("#404040")
        ax.spines["right"].set_color("#404040")

        ymin = 0
        ymax = max(values) * 1.15 if values else 1
        ax.set_ylim(ymin, ymax)

        self.breaks_fig_chart.subplots_adjust(left=0.20, right=0.98, top=0.9, bottom=0.2)
        self.breaks_canvas_chart.draw()

    # ----------------- TREND APP COMBO --------------------------
    def _update_trend_app_combo(self, apps):
        current_app = self._get_selected_app_key()

        self.trend_app_combo.blockSignals(True)
        self.trend_app_combo.clear()
        self.trend_app_combo.addItem("Всі застосунки", userData=None)

        seen = set()
        for app, title, cat, minutes in apps:
            if not app or app in seen:
                continue
            seen.add(app)
            self.trend_app_combo.addItem(app, userData=app)

        if current_app is not None:
            idx = self.trend_app_combo.findData(current_app)
            if idx >= 0:
                self.trend_app_combo.setCurrentIndex(idx)

        self.trend_app_combo.blockSignals(False)

    # ----------------- TREND MODE -------------------------------
    def _update_trend_for_current_mode(self):
        if not self._last_period:
            self._update_trend({})
            return

        start_str, end_str = self._last_period
        mode = self.trend_mode_combo.currentData()

        if mode == "category":
            cat_key = self._get_selected_category_key()
            if cat_key:
                daily_totals = self.repo.get_daily_totals_by_category(start_str, end_str, cat_key)
                color_key = cat_key
                title_suffix = f" – {CATEGORY_LABELS.get(cat_key, cat_key)}"
            else:
                daily_totals = self._last_daily_totals_all
                color_key = "work"
                title_suffix = ""
        elif mode == "app":
            app_key = self._get_selected_app_key()
            if app_key:
                daily_totals = self.repo.get_daily_totals_by_app(start_str, end_str, app_key)
                color_key = "other"
                title_suffix = f" – {app_key}"
            else:
                daily_totals = self._last_daily_totals_all
                color_key = "work"
                title_suffix = ""
        else:
            daily_totals = self._last_daily_totals_all
            color_key = "work"
            title_suffix = ""

        self._update_trend(daily_totals, color_key=color_key, title_suffix=title_suffix)

    def _get_selected_category_key(self):
        idx = self.trend_category_combo.currentIndex()
        if idx < 0:
            return None
        return self.trend_category_combo.currentData()

    def _get_selected_app_key(self):
        idx = self.trend_app_combo.currentIndex()
        if idx < 0:
            return None
        return self.trend_app_combo.currentData()

    def _on_trend_mode_changed(self, index):
        mode = self.trend_mode_combo.currentData()
        self.trend_category_combo.setEnabled(mode == "category")
        self.trend_app_combo.setEnabled(mode == "app")
        self._update_trend_for_current_mode()

    def _on_trend_category_changed(self, index):
        if self.trend_mode_combo.currentData() == "category":
            self._update_trend_for_current_mode()

    def _on_trend_app_changed(self, index):
        if self.trend_mode_combo.currentData() == "app":
            self._update_trend_for_current_mode()

    def _on_app_row_clicked(self, row, column):
        item = self.table_apps.item(row, 0)
        if not item:
            return
        app = item.text()
        idx = self.trend_app_combo.findData(app)
        if idx >= 0:
            self.trend_app_combo.setCurrentIndex(idx)
        if self.trend_mode_combo.currentData() == "app":
            self._update_trend_for_current_mode()

    # ----------------- PIE CHART -------------------------------
    def _update_pie(self, cat_minutes: dict[str, float]):
        from matplotlib.gridspec import GridSpec

        self.pie_fig.clear()

        gs = self.pie_fig.add_gridspec(1, 2, width_ratios=[2, 1], wspace=0.01)
        ax = self.pie_fig.add_subplot(gs[0, 0])       # пай-чарт
        leg_ax = self.pie_fig.add_subplot(gs[0, 1])   # легенда

        ax.set_facecolor("#202020")
        leg_ax.set_facecolor("#202020")
        self.pie_fig.patch.set_facecolor("#202020")

        if not cat_minutes:
            ax.text(
                0.5,
                0.5,
                "Немає даних",
                color="white",
                ha="center",
                va="center",
            )
            ax.axis("off")
            leg_ax.axis("off")
            self.pie_canvas.draw()
            return

        categories = list(cat_minutes.keys())
        values = [cat_minutes[c] for c in categories]
        colors = [CATEGORY_COLORS.get(c, CATEGORY_COLORS["other"]) for c in categories]

        total = sum(values) or 1.0

        def _fmt_pct(pct: float) -> str:
            if pct < 5:
                return ""
            return f"{pct:.0f}%"

        def _fmt_minutes_human(m: float) -> str:
            total_sec = int(m * 60)
            if total_sec < 60:
                return f"{total_sec} с"
            minutes = total_sec // 60
            hours = minutes // 60
            minutes = minutes % 60
            if hours > 0:
                if minutes > 0:
                    return f"{hours} год {minutes} хв"
                return f"{hours} год"
            return f"{minutes} хв"

        wedges, texts, autotexts = ax.pie(
            values,
            labels=None,
            colors=colors,
            startangle=90,
            autopct=_fmt_pct,
            textprops={"color": "white"},
        )

        for t in autotexts:
            t.set_color("white")
            t.set_fontsize(9)

        ax.set_title("Час за категоріями", color="white")
        ax.axis("equal")

        legend_labels = []
        for cat, val in zip(categories, values):
            pct = val / total * 100
            label = CATEGORY_LABELS.get(cat, cat)
            human = _fmt_minutes_human(val)
            legend_labels.append(f"{label} — {human} ({pct:.0f}%)")

        leg_ax.axis("off")
        legend = leg_ax.legend(
            wedges,
            legend_labels,
            loc="center left",
            bbox_to_anchor=(-0.05, 0.5),  
            fontsize=9,
            frameon=False,
        )


        for txt in legend.get_texts():
            txt.set_color("white")

        self.pie_fig.subplots_adjust(left=0.02, right=0.98, top=0.88, bottom=0.12)

        self.pie_canvas.draw()

    # ----------------- TREND CHART -----------------------------
    def _format_trend_ytick(self, value, pos):
        seconds = int(round(value * 60))
        if seconds <= 0:
            return "0"
        return format_duration_human(seconds)

    def _update_trend(
        self,
        daily_totals: dict[str, float],
        color_key: str | None = None,
        title_suffix: str = "",
    ):
        self.trend_fig.clear()
        ax = self.trend_fig.add_subplot(111)

        ax.set_facecolor("#202020")
        self.trend_fig.patch.set_facecolor("#202020")

        ax.yaxis.set_major_formatter(FuncFormatter(self._format_trend_ytick))
        ax.set_ylabel("Час", color="white")

        if not daily_totals:
            ax.text(
                0.5,
                0.5,
                "Немає даних за обраний період",
                color="white",
                ha="center",
                va="center",
            )
            ax.axis("off")
            self.trend_canvas.draw()
            return

        days = sorted(daily_totals.keys())
        values = [daily_totals[d] for d in days]

        x_idx = list(range(len(days)))
        labels = [f"{d[8:10]}.{d[5:7]}" for d in days]

        line_color = CATEGORY_COLORS.get(color_key or "work", "#4FC3F7")

        ax.plot(x_idx, values, marker="o", linewidth=2.0, color=line_color)

        ax.set_xticks(x_idx)
        ax.set_xticklabels(labels, rotation=0, ha="center", color="white")

        title = "Динаміка активності по днях"
        if title_suffix:
            title += title_suffix
        ax.set_title(title, color="white")

        ax.grid(True, linestyle="--", alpha=0.3, color="#AAAAAA")

        ax.tick_params(axis="y", colors="white")
        ax.spines["bottom"].set_color("white")
        ax.spines["left"].set_color("white")
        ax.spines["top"].set_color("#404040")
        ax.spines["right"].set_color("#404040")

        ymin = 0
        ymax = max(values) * 1.15 if values else 1
        ax.set_ylim(ymin, ymax)

        self.trend_fig.subplots_adjust(left=0.20, right=0.98, top=0.9, bottom=0.18)
        self.trend_canvas.draw()

    # ----------------- HEATMAP --------------------------------
    def _update_heatmap(self, heatmap_data: dict[str, dict[int, float]]):
        self.heatmap_fig.clear()
        ax = self.heatmap_fig.add_subplot(111)

        ax.set_facecolor("#202020")
        self.heatmap_fig.patch.set_facecolor("#202020")

        if not heatmap_data:
            ax.text(
                0.5,
                0.5,
                "Немає даних для побудови теплової карти",
                color="white",
                ha="center",
                va="center",
            )
            ax.axis("off")
            self.heatmap_canvas.draw()
            return

        days = sorted(heatmap_data.keys())
        if not days:
            ax.text(
                0.5,
                0.5,
                "Немає даних для побудови теплової карти",
                color="white",
                ha="center",
                va="center",
            )
            ax.axis("off")
            self.heatmap_canvas.draw()
            return

        active_hours = set()
        for d in days:
            for h, minutes in heatmap_data.get(d, {}).items():
                if minutes and minutes > 0:
                    active_hours.add(h)

        if not active_hours:
            ax.text(
                0.5,
                0.5,
                "Немає істотної активності за обраний період",
                color="white",
                ha="center",
                va="center",
            )
            ax.axis("off")
            self.heatmap_canvas.draw()
            return

        hours_list = sorted(active_hours)
        if len(hours_list) > 16:
            hours_list = list(range(24))

        data_matrix = []
        for h in hours_list:
            row = []
            for d in days:
                minutes = heatmap_data.get(d, {}).get(h, 0.0)
                row.append(minutes)
            data_matrix.append(row)

        img = ax.imshow(
            data_matrix,
            aspect="auto",
            origin="lower",
            cmap="magma",
        )

        x_idx = list(range(len(days)))
        x_labels = [f"{d[8:10]}.{d[5:7]}" for d in days]
        ax.set_xticks(x_idx)
        ax.set_xticklabels(x_labels, rotation=0, ha="center", color="white")

        y_idx = list(range(len(hours_list)))
        ax.set_yticks(y_idx)
        ax.set_yticklabels(
            [f"{h:02d}:00" for h in hours_list],
            color="white",
        )

        ax.set_xlabel("Дні", color="white")
        ax.set_ylabel("Години доби", color="white")
        ax.set_title("Активність по годинах", color="white")

        ax.tick_params(axis="x", colors="white")
        ax.tick_params(axis="y", colors="white")
        for spine in ax.spines.values():
            spine.set_color("#404040")

        self.heatmap_fig.subplots_adjust(left=0.18, right=0.98, top=0.9, bottom=0.18)

        cbar = self.heatmap_fig.colorbar(img, ax=ax)
        cbar.set_label("хвилини активності", color="white")
        cbar.ax.yaxis.set_tick_params(color="white")
        for t in cbar.ax.get_yticklabels():
            t.set_color("white")

        self.heatmap_canvas.draw()

    # ----------------- APPS TABLE ------------------------------
    def _update_apps_table(self, apps):
        self.table_apps.setRowCount(0)

        for row, (app, title, cat, minutes) in enumerate(apps):
            self.table_apps.insertRow(row)
            self.table_apps.setItem(row, 0, QTableWidgetItem(app))
            self.table_apps.setItem(row, 1, QTableWidgetItem(title))
            self.table_apps.setItem(
                row, 2, QTableWidgetItem(CATEGORY_LABELS.get(cat, cat))
            )
            seconds = int(round((minutes or 0) * 60))
            self.table_apps.setItem(row, 3, QTableWidgetItem(format_duration_human(seconds)))

        self.table_apps.resizeRowsToContents()

    # ----------------- AI REPORT -------------------------------
    def _on_ai_report(self):
        if not self._last_period:
            self.ai_output.setHtml(
                "<i>Спочатку виберіть період і натисніть «Оновити».</i>"
            )
            return

        data = {
            "period": self._last_period,
            "cat_minutes": self._cached_cat_minutes or {},
            "apps": self._cached_apps or [],
            "daily_totals": self._last_daily_totals_all or {},
            "heatmap_data": self._hourly_heatmap_data or {},
        }

        text = self.period_ai_service.build_period_report(data)
        html_text = self._format_ai_text_with_colors(text)
        self.ai_output.setHtml(html_text)

    def _format_ai_text_with_colors(self, text: str) -> str:
        if not text:
            return ""

        safe = html.escape(text)
        safe = safe.replace("\r\n", "\n")
        safe = safe.replace("\n\n", "<br><br>").replace("\n", "<br>")

        label_to_color = {
            label: CATEGORY_COLORS.get(key, "#FFFFFF")
            for key, label in CATEGORY_LABELS.items()
        }

        for label, color in label_to_color.items():
            safe = safe.replace(label, f'<span style="color:{color}">{label}</span>')

        return safe