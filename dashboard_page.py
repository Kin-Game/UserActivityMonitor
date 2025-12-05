from typing import List, Dict
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QScrollArea,
)
from PyQt6.QtCore import Qt

from ui.components.category_chart import CategoryChartWidget
from core.utils import format_duration_human


class DashboardPage(QWidget):


    def __init__(self, parent=None):
        super().__init__(parent)

        self._recommendations_plain: str = ""

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(16)

        # Карточка "Поточна активність"
        self.current_frame = QFrame()
        self.current_frame.setFrameShape(QFrame.Shape.StyledPanel)
        current_layout = QVBoxLayout()
        current_layout.setContentsMargins(12, 12, 12, 12)
        current_layout.setSpacing(8)

        title_label = QLabel("Поточна активність")
        title_label.setStyleSheet("font-weight: 600; font-size: 14px;")

        self.lbl_app = QLabel("Застосунок: —")
        self.lbl_title = QLabel("Вікно: —")
        self.lbl_category = QLabel("Категорія: —")
        self.lbl_duration = QLabel("Тривалість: —")
        self.lbl_idle = QLabel("Статус: —")

        for lbl in (
            self.lbl_app,
            self.lbl_title,
            self.lbl_category,
            self.lbl_duration,
            self.lbl_idle,
        ):
            lbl.setWordWrap(True)

        current_layout.addWidget(title_label)
        current_layout.addWidget(self.lbl_app)
        current_layout.addWidget(self.lbl_title)
        current_layout.addWidget(self.lbl_category)
        current_layout.addWidget(self.lbl_duration)
        current_layout.addWidget(self.lbl_idle)
        current_layout.addStretch(1)

        self.current_frame.setLayout(current_layout)

        # Компактний віджет "Баланс: робота / перерви (сьогодні)"
        self.balance_frame = QFrame()
        self.balance_frame.setFrameShape(QFrame.Shape.StyledPanel)
        balance_layout = QVBoxLayout()
        balance_layout.setContentsMargins(12, 12, 12, 12)
        balance_layout.setSpacing(6)

        balance_title = QLabel("Баланс: робота / перерви (сьогодні)")
        balance_title.setStyleSheet("font-weight: 600; font-size: 13px;")

        bars_layout = QHBoxLayout()
        bars_layout.setSpacing(4)

        self._bar_work = QFrame()
        self._bar_work.setFixedHeight(10)
        self._bar_work.setStyleSheet(
            "background-color: #4CAF50; border-radius: 4px;"
        )

        self._bar_breaks = QFrame()
        self._bar_breaks.setFixedHeight(10)
        self._bar_breaks.setStyleSheet(
            "background-color: #B0BEC5; border-radius: 4px;"
        )

        bars_layout.addWidget(self._bar_work)
        bars_layout.addWidget(self._bar_breaks)
        self._balance_bars_layout = bars_layout

        self.lbl_balance_caption = QLabel("Поки що немає даних за сьогодні.")
        self.lbl_balance_caption.setStyleSheet(
            "font-size: 11px; color: #cccccc;"
        )
        self.lbl_balance_caption.setWordWrap(True)

        balance_layout.addWidget(balance_title)
        balance_layout.addLayout(bars_layout)
        balance_layout.addWidget(self.lbl_balance_caption)
        self.balance_frame.setLayout(balance_layout)

        left_col_widget = QWidget()
        left_col_layout = QVBoxLayout(left_col_widget)
        left_col_layout.setContentsMargins(0, 0, 0, 0)
        left_col_layout.setSpacing(8)
        left_col_layout.addWidget(self.current_frame, 3)
        left_col_layout.addWidget(self.balance_frame, 1)

        self.chart_widget = CategoryChartWidget()

        top_layout.addWidget(left_col_widget, 1)
        top_layout.addWidget(self.chart_widget, 2)

        # -------- Нижній рядок: таблиця + рекомендації --------

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(16)

        # Таблиця "Активність за сьогодні"
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Початок", "Кінець", "Тривалість", "Застосунок", "Вікно", "Категорія"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)

        # Панель "Рекомендації"
        self.recommend_frame = QFrame()
        self.recommend_frame.setFrameShape(QFrame.Shape.StyledPanel)
        rec_layout = QVBoxLayout()
        rec_layout.setContentsMargins(12, 12, 12, 12)
        rec_layout.setSpacing(8)

        rec_title = QLabel("Рекомендації")
        rec_title.setStyleSheet("font-weight: 600; font-size: 14px;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.lbl_recommendations = QLabel(
            "Поки що рекомендацій немає.\n"
            "Запусти моніторинг, попрацюй трохи, а потім натисни «Оновити поради»."
        )
        self.lbl_recommendations.setWordWrap(True)

        scroll_inner = QWidget()
        inner_layout = QVBoxLayout()
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.addWidget(self.lbl_recommendations)
        scroll_inner.setLayout(inner_layout)

        scroll.setWidget(scroll_inner)

        self.btn_copy_recommendations = QPushButton("Скопіювати")
        self.btn_copy_recommendations.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.btn_refresh_recommendations = QPushButton("Оновити поради")
        self.btn_refresh_recommendations.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addWidget(self.btn_copy_recommendations)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_refresh_recommendations)

        rec_layout.addWidget(rec_title)
        rec_layout.addWidget(scroll)
        rec_layout.addLayout(btn_row)

        self.recommend_frame.setLayout(rec_layout)

        bottom_layout.addWidget(self.table, 3)
        bottom_layout.addWidget(self.recommend_frame, 1)

        main_layout.addLayout(top_layout)
        main_layout.addLayout(bottom_layout)

        self.setLayout(main_layout)

    # -------- Допоміжні форматери --------

    @staticmethod
    def _format_time(iso_str: str) -> str:
        if not iso_str:
            return ""
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime("%H:%M:%S")
        except Exception:
            if len(iso_str) >= 19:
                return iso_str[11:19]
            return iso_str

    @staticmethod
    def _parse_duration_seconds(raw: str) -> int:
        if raw is None:
            return 0
        digits = "".join(ch for ch in str(raw) if ch.isdigit())
        return int(digits) if digits else 0

    @staticmethod
    def _format_duration(seconds: int) -> str:
        return format_duration_human(seconds)

    # -------- Публічні методи --------

    def update_current_activity(
        self,
        app: str,
        title: str,
        category: str | None,
        duration_sec: int,
        is_idle: bool = False,
    ):
        self.lbl_app.setText(f"Застосунок: {app or '—'}")
        self.lbl_title.setText(f"Вікно: {title or '—'}")

        cat_text = category if category else "—"
        self.lbl_category.setText(f"Категорія: {cat_text}")

        self.lbl_duration.setText(
            f"Тривалість: {self._format_duration(duration_sec)}"
        )

        if is_idle:
            self.lbl_idle.setText("Статус: перерва / idle")
            self.lbl_idle.setStyleSheet("color: #ffcc00;")
        else:
            self.lbl_idle.setText("Статус: активний")
            self.lbl_idle.setStyleSheet("color: #a0ffa0;")

    def refresh_table(self, rows: List[Dict[str, str]]):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            start_iso = row.get("start", "")
            end_iso = row.get("end", "")
            duration_raw = row.get("duration", "")

            start_fmt = self._format_time(start_iso)
            end_fmt = self._format_time(end_iso)
            seconds = self._parse_duration_seconds(duration_raw)
            duration_fmt = self._format_duration(seconds)

            app = row.get("app", "")
            title = row.get("title", "")
            category = row.get("category", "")

            item_start = QTableWidgetItem(start_fmt)
            item_end = QTableWidgetItem(end_fmt)
            item_duration = QTableWidgetItem(duration_fmt)
            item_app = QTableWidgetItem(app)
            item_title = QTableWidgetItem(title)
            item_category = QTableWidgetItem(category)

            if title:
                item_title.setToolTip(title)

            self.table.setItem(r, 0, item_start)
            self.table.setItem(r, 1, item_end)
            self.table.setItem(r, 2, item_duration)
            self.table.setItem(r, 3, item_app)
            self.table.setItem(r, 4, item_title)
            self.table.setItem(r, 5, item_category)

        self.table.setSortingEnabled(True)
        self.table.sortItems(0, Qt.SortOrder.AscendingOrder)

    def update_category_chart(self, data: Dict[str, float]):
        self.chart_widget.update_data(data)

    def update_activity_breaks_summary(self, active_sec: int, break_sec: int):
        """Оновлює компактний віджет балансу робота/перерви на дашборді."""
        try:
            active_sec = int(active_sec or 0)
        except Exception:
            active_sec = 0
        try:
            break_sec = int(break_sec or 0)
        except Exception:
            break_sec = 0

        if active_sec < 0:
            active_sec = 0
        if break_sec < 0:
            break_sec = 0

        total = active_sec + break_sec
        if total <= 0:
            # Стандартний стан, коли ще немає даних за сьогодні
            self._balance_bars_layout.setStretch(0, 1)
            self._balance_bars_layout.setStretch(1, 1)
            self.lbl_balance_caption.setText("Поки що немає даних за сьогодні.")
            return

        active_pct = active_sec / total
        break_pct = break_sec / total

        a_stretch = max(int(active_pct * 100), 1)
        b_stretch = max(int(break_pct * 100), 1)
        self._balance_bars_layout.setStretch(0, a_stretch)
        self._balance_bars_layout.setStretch(1, b_stretch)

        caption = (
            f"Активність: {format_duration_human(active_sec)} "
            f"({active_pct * 100:.0f}%)   •   "
            f"Перерви: {format_duration_human(break_sec)} "
            f"({break_pct * 100:.0f}%)"
        )
        self.lbl_balance_caption.setText(caption)

    # -------- Рекомендації --------

    @staticmethod
    def _highlight_categories(text: str) -> str:
        html = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        html = html.replace("\n", "<br>")

        color_map = {
            "робота": "#4A90E2",        # work
            "ігри": "#F5A623",          # games
            "медіа": "#7ED321",         # media
            "серфінг": "#50E3C2",       # browsing
            "спілкування": "#BD10E0",   # communication
            "соцмережі": "#F8E71C",     # social
            "навчання": "#B8E986",      # education
            "інше": "#9B9B9B",          # other
        }

        for word, color in color_map.items():
            html = html.replace(
                word,
                f'<span style="color:{color}; font-weight:600;">{word}</span>',
            )

        return html


    def set_recommendations_text(self, text: str):
        self._recommendations_plain = text or ""
        html = self._highlight_categories(self._recommendations_plain)
        self.lbl_recommendations.setText(html)

    def get_recommendations_plain_text(self) -> str:
        return self._recommendations_plain
