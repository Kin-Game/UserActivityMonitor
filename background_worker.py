from PyQt6.QtCore import QThread, pyqtSignal

from core.tracker import ActiveWindowTracker
from core.utils import now
from storage.json_repo import JSONRepository
from core.classifier import Classifier
from storage.sqlite_repo import SQLiteSessionRepository
from core.settings_service import SettingsService

import time
from typing import Optional


class BackgroundWorker(QThread):

    session_completed = pyqtSignal(dict)
    current_activity = pyqtSignal(dict)

    def __init__(self, settings: SettingsService, interval: int = 5):
        super().__init__()
        self.interval = interval

        # ---------- Налаштування користувача ----------
        self.settings = settings
        self.settings.settings_changed.connect(self._on_settings_changed)

        self.idle_timeout: int = self.settings.get("idle_timeout_sec", 300)
        self.passive_apps = self.settings.get("passive_allowed_apps", [])
        self.passive_categories = self.settings.get("passive_allowed_categories", [])

        # ---------- Сервіси ----------
        self.tracker = ActiveWindowTracker()
        self.repo = JSONRepository()
        self.sqlite_repo = SQLiteSessionRepository()
        self.classifier = Classifier()

        # ---------- Стан сесії ----------
        self._running: bool = True
        self.current_session: Optional[dict] = None
        self.current_start_dt = None

        # ---------- Стан для перерв ----------
        self._is_idle: bool = False
        self._current_break_start: Optional[int] = None
        self._last_active_category: Optional[str] = None

    # ======================================================
    #            РЕАКЦІЯ НА ЗМІНУ НАЛАШТУВАНЬ
    # ======================================================
    def _on_settings_changed(self, changed: dict):

        if "idle_timeout_sec" in changed:
            self.idle_timeout = changed["idle_timeout_sec"]

        if "passive_allowed_apps" in changed:
            self.passive_apps = changed["passive_allowed_apps"]

        if "passive_allowed_categories" in changed:
            self.passive_categories = changed["passive_allowed_categories"]

    # ======================================================
    #            RULE-MATCHING ДЛЯ PASSIVE APPS
    # ======================================================
    def _match_app_rule(self, app: str, title: str, rule: str) -> bool:

        rule = rule.lower()
        app = app.lower()
        title = title.lower()

        if "::" not in rule:
            return rule == app

        exe, domain = rule.split("::", 1)
        return exe == app and domain in title

    # ======================================================
    #           ЛОГІКА ПЕРЕХОДІВ IDLE → BREAKS
    # ======================================================
    def _handle_idle_transition(self, is_idle_now: bool, now_ts: int) -> None:
  
        was_idle = self._is_idle

        # ACTIVE → IDLE — початок перерви
        if not was_idle and is_idle_now:
            self._current_break_start = now_ts

        # IDLE → ACTIVE — кінець перерви
        elif was_idle and not is_idle_now:
            if self._current_break_start is not None:
                try:
                    self.sqlite_repo.save_break(
                        start_ts=self._current_break_start,
                        end_ts=now_ts,
                        last_category=self._last_active_category,
                    )
                except Exception as e:
                    # Тут можна під'єднати твій логгер замість print
                    print("[BackgroundWorker] Failed to save break:", repr(e))

                self._current_break_start = None

        self._is_idle = is_idle_now

    # ======================================================
    #                      MAIN LOOP
    # ======================================================
    def run(self):
        while self._running:
            # 1) Зчитуємо активне вікно, idle-стан та чи воно повноекранне
            app, title = self.tracker.get_active_window_info()
            is_fullscreen = self.tracker.is_foreground_fullscreen()
            raw_idle = self.tracker.is_user_idle(self.idle_timeout)

            now_dt = now()
            now_ts = int(now_dt.timestamp())

            # Категорія для passive_categories — тільки якщо сесія вже класифікована
            category = self.current_session["category"] if self.current_session else None

            # 2) Визначаємо, чи застосунок / категорія пасивні
            passive = (
                (category in self.passive_categories)
                or any(self._match_app_rule(app, title, r) for r in self.passive_apps)
            )

            # Кінцевий idle, який іде в UI та в breaks
            effective_idle = raw_idle and not passive

            # 3) Оновлюємо breaks поверх idle-переходів
            self._handle_idle_transition(effective_idle, now_ts)

            # 4) Логіка сесій
            if self.current_session is None:
                # Перша сесія
                self.current_start_dt = now_dt
                self.current_session = {
                    "start": now_dt.isoformat(),
                    "end": None,
                    "app": app,
                    "title": title,
                    "category": None,
                    "idle": effective_idle,
                }
            else:
                # Зміна активного вікна → закриваємо попередню сесію
                if (
                    app != self.current_session["app"]
                    or title != self.current_session["title"]
                ):
                    self.current_session["idle"] = effective_idle
                    self._finish_current_session(now_dt)

                    self.current_start_dt = now_dt
                    self.current_session = {
                        "start": now_dt.isoformat(),
                        "end": None,
                        "app": app,
                        "title": title,
                        "category": None,
                        "idle": effective_idle,
                    }

            # 5) Оновлюємо статус для UI
            duration_sec = (
                int((now_dt - self.current_start_dt).total_seconds())
                if self.current_start_dt
                else 0
            )

            self.current_activity.emit(
                {
                    "app": app,
                    "title": title,
                    "idle": effective_idle,
                    "duration_sec": duration_sec,
                    "category": self.current_session.get("category"),
                    "is_fullscreen": is_fullscreen,
                }
            )


            time.sleep(self.interval)

        # При зупинці потоку — закриваємо останню сесію
        if self.current_session and self.current_session["end"] is None:
            self._finish_current_session(now())

    # ======================================================
    #                   ЗАКРИТТЯ СЕСІЇ
    # ======================================================
    def _finish_current_session(self, end_dt):
        self.current_session["end"] = end_dt.isoformat()

        try:
            duration = int((end_dt - self.current_start_dt).total_seconds())
        except Exception:
            duration = 0

        self.current_session["duration_sec"] = duration

        # Класифікація
        app = self.current_session["app"]
        title = self.current_session["title"]
        cat = self.classifier.classify(app, title)
        self.current_session["category"] = cat

        # Медіа / пасивні категорії — ніколи не idle
        if cat in self.passive_categories:
            self.current_session["idle"] = False

        # Оновлюємо останню активну категорію (для майбутніх breaks)
        if not self.current_session["idle"]:
            self._last_active_category = cat

        # Збереження сесії
        self.repo.save_session(self.current_session)
        self.sqlite_repo.save_session(self.current_session)

        # Сигнал для UI
        self.session_completed.emit(self.current_session.copy())

    def stop(self):
        self._running = False
