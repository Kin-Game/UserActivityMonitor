from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QStackedWidget,
    QApplication,
)

from config.settings import DB_PATH  # шлях до SQLite / конфігів

from core.analytics import AnalyticsService
from core.recommendations import RecommendationService
from core.rule_engine import RuleEngine

from ui.dashboard_page import DashboardPage
from ui.stats_page import StatsPage
from ui.settings_page import SettingsPage
from ui.components.sidebar import Sidebar
from ui.components.toast import Toast

from services.background_worker import BackgroundWorker
from storage.json_repo import JSONRepository

from storage.settings_repo import SettingsRepository
from core.settings_service import SettingsService


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("User Activity Monitor")
        self.resize(1200, 800)

        # Шлях до БД
        self.db_path = DB_PATH

        # Кеш категорій: (app, title) -> category
        self.category_cache: dict[tuple[str, str], str] = {}

        # Toasts
        self._toasts: list[Toast] = []

        # Стан повноекранного застосунку та черга відкладених тостів
        self._is_fullscreen_app: bool = False
        self._deferred_toasts: list[tuple[str, str]] = []


        # ---- Sidebar ----
        self.sidebar = Sidebar()

        # ---- Pages ----
        self.stack = QStackedWidget()
        self.dashboard_page = DashboardPage(parent=self)
        self.stats_page = StatsPage(parent=self)
        self.settings_page = SettingsPage(parent=self)

        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.stats_page)
        self.stack.addWidget(self.settings_page)

        # ---- Layout ----
        central = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack)
        central.setLayout(layout)
        self.setCentralWidget(central)

        # ---- Навігація ----
        self.sidebar.page_selected.connect(self.on_page_selected)

        # ---- Services ----
        self.json_repo = JSONRepository()
        self.analytics = AnalyticsService()
        self.recommendations = RecommendationService()
        self.rule_engine = RuleEngine()

        # ---- Settings service (для idle, пасивних застосунків тощо) ----
        self.settings_repo = SettingsRepository(self.db_path)
        self.settings_service = SettingsService(self.settings_repo)

        # ---- Background worker ----
        self.worker = BackgroundWorker(
            settings=self.settings_service,
            interval=5,
        )
        self.worker.current_activity.connect(self.on_current_activity)
        self.worker.session_completed.connect(self.on_session_completed)
        self.worker.start()

        # ---- Кнопки Dashboard ----
        self.dashboard_page.btn_refresh_recommendations.clicked.connect(
            self.on_refresh_recommendations
        )
        self.dashboard_page.btn_copy_recommendations.clicked.connect(
            self.on_copy_recommendations
        )

        # Початкове заповнення
        self.refresh_today_table()
        self.refresh_category_chart()
        self.refresh_today_balance_widget()

    # =====================================================
    #                     СЛОТИ
    # =====================================================

    def on_page_selected(self, index: int):
        self.stack.setCurrentIndex(index)

    def on_current_activity(self, payload: dict):
        app = payload.get("app", "—")
        title = payload.get("title", "—")
        duration_sec = payload.get("duration_sec", 0)
        idle = payload.get("idle", False)
        is_fullscreen = payload.get("is_fullscreen", False)

        category = payload.get("category")
        if not category:
            category = self.category_cache.get((app, title))


        was_fullscreen = self._is_fullscreen_app
        self._is_fullscreen_app = is_fullscreen

        if was_fullscreen and not is_fullscreen and self._deferred_toasts:
            for text, level in self._deferred_toasts:
                self.show_toast(text, level)
            self._deferred_toasts.clear()

        self.dashboard_page.update_current_activity(
            app=app,
            title=title,
            category=category,
            duration_sec=duration_sec,
            is_idle=idle,
        )

        if category and duration_sec > 0:
            res = self.rule_engine.check_live_category(category, duration_sec)
            if res:
                text, level = res
                if self._is_fullscreen_app:
                    self._deferred_toasts.append((text, level))
                else:
                    self.show_toast(text, level)


    def on_session_completed(self, session: dict):
        """
        Після завершення сесії:
        - оновлюємо кеш
        - оновлюємо таблицю
        - оновлюємо графік
        - оновлюємо баланс робота/перерви
        - перевіряємо ліміти правил
        """
        app = session.get("app", "")
        title = session.get("title", "")
        category = session.get("category")

        if category:
            self.category_cache[(app, title)] = category

        self.refresh_today_table()
        self.refresh_category_chart()
        self.refresh_today_balance_widget()

        res = self.rule_engine.check_overall()
        if res:
            text, level = res
            if self._is_fullscreen_app:
                self._deferred_toasts.append((text, level))
            else:
                self.show_toast(text, level)


    # =====================================================
    #                     Допоміжні
    # =====================================================

    def refresh_today_table(self):
        raw_sessions = self.json_repo.get_today_sessions()
        rows = []

        for s in raw_sessions:
            start = s.get("start")
            end = s.get("end")
            duration_sec = s.get("duration_sec", None)

            if duration_sec is None and start and end:
                try:
                    start_dt = datetime.fromisoformat(start)
                    end_dt = datetime.fromisoformat(end)
                    duration_sec = int((end_dt - start_dt).total_seconds())
                except Exception:
                    duration_sec = 0

            app = s.get("app", "")
            title = s.get("title", "")
            category = s.get("category") or ""

            # Cache
            if category:
                self.category_cache[(app, title)] = category

            rows.append(
                {
                    "start": start or "",
                    "end": end or "",
                    "duration": f"{int(duration_sec)}s"
                    if duration_sec is not None
                    else "",
                    "app": app,
                    "title": title,
                    "category": category,
                }
            )

        self.dashboard_page.refresh_table(rows)

    def refresh_category_chart(self):
        data = self.analytics.get_today_category_minutes()
        self.dashboard_page.update_category_chart(data)

    def refresh_today_balance_widget(self):
        data = self.analytics.get_today_activity_vs_breaks()
        self.dashboard_page.update_activity_breaks_summary(
            data.get("active_sec", 0),
            data.get("break_sec", 0),
        )

    def on_refresh_recommendations(self):
        text = self.recommendations.build_today_recommendations()
        self.dashboard_page.set_recommendations_text(text)

    def on_copy_recommendations(self):
        text = self.dashboard_page.get_recommendations_plain_text() or ""
        QApplication.clipboard().setText(text)

    # =====================================================
    #                     Toasts
    # =====================================================

    def show_toast(self, text: str, level: str):
        index = len(self._toasts)
        toast = Toast(self, text, level, index=index)
        toast.closed.connect(self.on_toast_closed)

        self._toasts.append(toast)
        toast.show()

    def on_toast_closed(self, toast: Toast):
        try:
            self._toasts.remove(toast)
        except ValueError:
            return

        for i, t in enumerate(self._toasts):
            t.index = i
            t.reposition()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_toasts"):
            for t in self._toasts:
                t.reposition()

    # =====================================================
    #                     Close
    # =====================================================

    def closeEvent(self, event):
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)
        super().closeEvent(event)
