from typing import Dict
from pathlib import Path
import json
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QFormLayout,
    QCheckBox,
    QSpinBox,
    QPushButton,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QSizePolicy,
)
from PyQt6.QtCore import Qt

from storage.limits_repo import CategoryLimitsRepository, CATEGORIES
from storage.app_category_profile_repo import AppCategoryProfileRepository
from config.ai_settings import load_ai_settings, save_ai_settings

TOAST_SETTINGS_PATH = Path("data/notification_settings.json")


def load_toast_settings() -> dict:
    defaults = {
        "duration_ms": 5000,
        "position": "bottom-right",
        "cooldown_minutes": 5,
        "show_warning": True,
        "show_critical": True,
        "sound_enabled": False,
    }
    try:
        if TOAST_SETTINGS_PATH.is_file():
            with open(TOAST_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            defaults.update(data.get("toast", {}))
    except Exception:
        pass
    return defaults


def save_toast_settings(cfg: dict) -> None:
    TOAST_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TOAST_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump({"toast": cfg}, f, ensure_ascii=False, indent=2)


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # --- репозиторії ---
        self.repo = CategoryLimitsRepository()
        self.app_repo = AppCategoryProfileRepository()
        self._rows: Dict[str, Dict[str, object]] = {}

        self._toast_position_map = {
            "Нижній правий кут": "bottom-right",
            "Нижній лівий кут": "bottom-left",
            "Верхній правий кут": "top-right",
            "Верхній лівий кут": "top-left",
        }

        # для розкладу профілів
        self._weekday_keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        self._weekday_labels = {
            "mon": "Понеділок",
            "tue": "Вівторок",
            "wed": "Середа",
            "thu": "Четвер",
            "fri": "Пʼятниця",
            "sat": "Субота",
            "sun": "Неділя",
        }
        self._weekday_profile_combos: Dict[str, QComboBox] = {}

        # налаштування idle / passive
        from storage.settings_repo import SettingsRepository
        from core.settings_service import SettingsService
        from config.settings import DB_PATH

        self.settings_repo_idle = SettingsRepository(DB_PATH)
        self.settings_idle = SettingsService(self.settings_repo_idle)

        # ===================================================================
        # ROOT: 2 КОЛОНКИ
        # ===================================================================
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(24)

        left_col = QVBoxLayout()
        left_col.setSpacing(16)
        right_col = QVBoxLayout()
        right_col.setSpacing(16)

        root.addLayout(left_col, stretch=3)
        root.addLayout(right_col, stretch=2)

        # -------------------------------------------------------------------
        # ЛІВА КОЛОНКА: ліміти, розклад, категорії застосунків
        # -------------------------------------------------------------------

        # --- Ліміти часу та профілі ---
        limits_group = QGroupBox("Ліміти часу та профілі")
        limits_layout = QVBoxLayout(limits_group)
        limits_layout.setSpacing(8)

        title = QLabel("Налаштування лімітів часу")
        title.setStyleSheet("font-weight: 600; font-size: 16px;")

        desc = QLabel(
            "Тут можна задати добові ліміти часу для різних категорій активності. "
            "Якщо ліміт увімкнено, система відстежуватиме перевищення та "
            "формуватиме рекомендації на основі фактичного використання."
        )
        desc.setWordWrap(True)

        limits_layout.addWidget(title)
        limits_layout.addWidget(desc)

        # кнопка збереження лімітів
        btn_save_limits = QPushButton("Зберегти ліміти")
        btn_save_limits.clicked.connect(self.save_limits)

        # профілі + кнопка збереження лімітів в одному рядку
        profiles_row = QHBoxLayout()
        profiles_row.setSpacing(8)

        lbl_profile = QLabel("Профіль:")
        self.profile_combo = QComboBox()
        self.btn_profile_new = QPushButton("Новий")
        self.btn_profile_rename = QPushButton("Перейменувати")
        self.btn_profile_delete = QPushButton("Видалити")

        self.btn_profile_new.clicked.connect(self.on_profile_new)
        self.btn_profile_rename.clicked.connect(self.on_profile_rename)
        self.btn_profile_delete.clicked.connect(self.on_profile_delete)
        self.profile_combo.currentTextChanged.connect(self.on_profile_changed)

        profiles_row.addWidget(lbl_profile)
        profiles_row.addWidget(self.profile_combo, stretch=1)
        profiles_row.addWidget(self.btn_profile_new)
        profiles_row.addWidget(self.btn_profile_rename)
        profiles_row.addWidget(self.btn_profile_delete)
        profiles_row.addStretch()
        profiles_row.addWidget(btn_save_limits)

        limits_layout.addLayout(profiles_row)

        # таблиця лімітів
        limits_frame = QFrame()
        limits_frame.setFrameShape(QFrame.Shape.StyledPanel)
        limits_form = QFormLayout(limits_frame)
        limits_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        limits_form.setHorizontalSpacing(20)
        limits_form.setVerticalSpacing(6)

        limits = self.repo.get_all_limits()
        human_names = {
            "work": "Робота",
            "games": "Ігри",
            "media": "Медіа",
            "browsing": "Серфінг",
            "communication": "Спілкування",
            "social": "Соцмережі",
            "education": "Навчання",
            "other": "Інше",
        }

        for cat in CATEGORIES:
            cfg = limits.get(cat, {"limit_minutes": 0, "enabled": 0})
            limit_min = int(cfg.get("limit_minutes") or 0)

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            chk = QCheckBox("Контролювати")
            chk.setChecked(bool(cfg.get("enabled")))

            spin = QSpinBox()
            spin.setRange(0, 1440)
            spin.setValue(limit_min)
            spin.setSuffix(" хв/день")

            row_layout.addWidget(chk)
            row_layout.addWidget(spin)
            row_layout.addStretch()

            limits_form.addRow(human_names[cat] + ":", row_widget)

            self._rows[cat] = {"chk": chk, "spin": spin}

        limits_layout.addWidget(limits_frame)

        # --- Розклад профілів по днях ---
        schedule_group = QGroupBox("Розклад профілів по днях")
        schedule_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )

        schedule_form = QFormLayout(schedule_group)
        schedule_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        schedule_form.setHorizontalSpacing(20)
        schedule_form.setVerticalSpacing(4)

        btn_save_schedule = QPushButton("Зберегти розклад")
        btn_save_schedule.clicked.connect(self.save_weekly_schedule_ui)

        for key in self._weekday_keys:
            combo = QComboBox()
            combo.setMaximumWidth(220)
            self._weekday_profile_combos[key] = combo

            if key == "sun":
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(8)
                row_layout.addWidget(combo)
                row_layout.addStretch()
                row_layout.addWidget(btn_save_schedule)

                schedule_form.addRow(self._weekday_labels[key] + ":", row_widget)
            else:
                schedule_form.addRow(self._weekday_labels[key] + ":", combo)

        limits_layout.addWidget(schedule_group)

        left_col.addWidget(limits_group)

        # --- Категорії застосунків ---
        apps_group = QGroupBox("Категорії застосунків")
        apps_layout = QVBoxLayout(apps_group)

        self.table_apps = QTableWidget(0, 3)
        self.table_apps.setHorizontalHeaderLabels(
            ["Exe", "Заголовок містить", "Категорія"]
        )
        self.table_apps.horizontalHeader().setStretchLastSection(True)
        self.table_apps.setMinimumHeight(120)

        apps_layout.addWidget(self.table_apps)

        apps_btns = QHBoxLayout()
        btn_add_rule = QPushButton("Додати правило")
        btn_del_rule = QPushButton("Видалити")
        btn_apply_rules = QPushButton("Застосувати категорії")

        btn_add_rule.clicked.connect(self.on_add_app_rule)
        btn_del_rule.clicked.connect(self.on_delete_app_rule)
        btn_apply_rules.clicked.connect(self.on_apply_app_rules)

        apps_btns.addWidget(btn_add_rule)
        apps_btns.addWidget(btn_del_rule)
        apps_btns.addStretch()
        apps_btns.addWidget(btn_apply_rules)

        apps_layout.addLayout(apps_btns)

        left_col.addWidget(apps_group)
        left_col.addStretch()

        # -------------------------------------------------------------------
        # ПРАВА КОЛОНКА: AI, Idle, toast, пасивні застосунки, пасивні категорії
        # -------------------------------------------------------------------

        # --- AI-класифікація ---
        ai_group = QGroupBox("AI-класифікація")
        ai_vbox = QVBoxLayout(ai_group)
        ai_form = QFormLayout()
        ai_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.ai_mode_combo = QComboBox()
        self._ai_mode_map: Dict[str, str] = {
            "Комбінований (правила + AI + історія)": "hybrid",
            "Лише правила": "rules_only",
            "Лише AI (Ollama)": "llm_only",
        }
        for lbl in self._ai_mode_map.keys():
            self.ai_mode_combo.addItem(lbl)

        self.ai_history_checkbox = QCheckBox("Використовувати історію (самонавчання)")

        ai_desc = QLabel(
            "Комбінований режим спочатку застосовує ручні правила, потім AI, "
            "а за потреби коригує результат на основі історії використання."
        )
        ai_desc.setWordWrap(True)

        ai_form.addRow("Режим класифікації:", self.ai_mode_combo)
        ai_form.addRow(self.ai_history_checkbox)
        ai_vbox.addLayout(ai_form)
        ai_vbox.addWidget(ai_desc)

        btn_save_ai = QPushButton("Зберегти AI-налаштування")
        btn_save_ai.clicked.connect(self.save_ai_settings_ui)
        ai_vbox.addWidget(btn_save_ai, alignment=Qt.AlignmentFlag.AlignRight)
        ai_vbox.addStretch()

        right_col.addWidget(ai_group)

        # --- Idle / AFK ---
        idle_group = QGroupBox("Idle / AFK налаштування")
        idle_layout = QVBoxLayout(idle_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Час до AFK:"))
        self.spin_idle = QSpinBox()
        self.spin_idle.setRange(10, 3600)
        self.spin_idle.setSuffix(" сек")
        self.spin_idle.setValue(self.settings_idle.get("idle_timeout_sec", 300))
        row1.addWidget(self.spin_idle)
        row1.addStretch()

        btn_idle_save = QPushButton("Зберегти")
        btn_idle_save.clicked.connect(self._save_idle_settings)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Мінімальна тривалість перерви для відображення (с):"))
        self.spin_break_min = QSpinBox()
        self.spin_break_min.setRange(0, 3600)
        self.spin_break_min.setSuffix(" с")
        self.spin_break_min.setValue(
            self.settings_idle.get("break_min_visible_sec", 5)
        )
        row2.addWidget(self.spin_break_min)
        row2.addStretch()
        row2.addWidget(btn_idle_save)

        idle_layout.addLayout(row1)
        idle_layout.addLayout(row2)

        right_col.addWidget(idle_group)

        # --- Сповіщення (toast) ---
        toast_group = QGroupBox("Сповіщення (toast)")
        toast_vbox = QVBoxLayout(toast_group)
        toast_layout = QFormLayout()
        toast_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.toast_duration_spin = QSpinBox()
        self.toast_duration_spin.setRange(1, 20)
        self.toast_duration_spin.setSuffix(" с")

        self.toast_position_combo = QComboBox()
        self.toast_position_combo.addItems(self._toast_position_map.keys())

        self.toast_cooldown_spin = QSpinBox()
        self.toast_cooldown_spin.setRange(0, 60)
        self.toast_cooldown_spin.setSuffix(" хв")

        self.toast_warn_checkbox = QCheckBox("Попередження — жовта зона")
        self.toast_critical_checkbox = QCheckBox("Сповіщення — червона зона")
        self.toast_sound_checkbox = QCheckBox("Звук сповіщення")

        toast_layout.addRow("Тривалість показу:", self.toast_duration_spin)
        toast_layout.addRow("Позиція:", self.toast_position_combo)
        toast_layout.addRow("Інтервал між сповіщеннями:", self.toast_cooldown_spin)
        toast_layout.addRow(self.toast_warn_checkbox)
        toast_layout.addRow(self.toast_critical_checkbox)
        toast_layout.addRow(self.toast_sound_checkbox)

        toast_vbox.addLayout(toast_layout)

        btn_save_toast = QPushButton("Зберегти сповіщення")
        toast_btn_row = QHBoxLayout()
        toast_btn_row.addStretch()
        toast_btn_row.addWidget(btn_save_toast)
        toast_vbox.addLayout(toast_btn_row)

        btn_save_toast.clicked.connect(self.save_toast_settings_ui)

        right_col.addWidget(toast_group)

        # --- Пасивно активні застосунки ---
        passive_apps_group = QGroupBox("Пасивно активні застосунки")
        passive_apps_layout = QVBoxLayout(passive_apps_group)

        self.table_passive_apps = QTableWidget(0, 1)
        self.table_passive_apps.setHorizontalHeaderLabels(["Rule"])
        self.table_passive_apps.horizontalHeader().setStretchLastSection(True)
        self.table_passive_apps.setMinimumHeight(120)

        passive_apps_layout.addWidget(self.table_passive_apps)

        btn_pa_add = QPushButton("Додати")
        btn_pa_del = QPushButton("Видалити")

        passive_btns = QHBoxLayout()
        passive_btns.addWidget(btn_pa_add)
        passive_btns.addWidget(btn_pa_del)
        passive_btns.addStretch()

        passive_apps_layout.addLayout(passive_btns)

        right_col.addWidget(passive_apps_group)

        def load_passive_apps():
            rules = self.settings_idle.get("passive_allowed_apps", [])
            self.table_passive_apps.setRowCount(0)
            for r in rules:
                row = self.table_passive_apps.rowCount()
                self.table_passive_apps.insertRow(row)
                self.table_passive_apps.setItem(row, 0, QTableWidgetItem(r))

        def add_passive_rule():
            from PyQt6.QtWidgets import QInputDialog

            rule, ok = QInputDialog.getText(
                self, "Rule", "vlc.exe або chrome.exe::youtube.com:"
            )
            if ok and rule.strip():
                rules = self.settings_idle.get("passive_allowed_apps", [])
                rules.append(rule.strip())
                self.settings_idle.set("passive_allowed_apps", rules)
                load_passive_apps()

        def del_passive_rule():
            r = self.table_passive_apps.currentRow()
            if r >= 0:
                item = self.table_passive_apps.item(r, 0)
                if not item:
                    return
                rule = item.text()
                rules = self.settings_idle.get("passive_allowed_apps", [])
                if rule in rules:
                    rules.remove(rule)
                    self.settings_idle.set("passive_allowed_apps", rules)
                    load_passive_apps()

        btn_pa_add.clicked.connect(add_passive_rule)
        btn_pa_del.clicked.connect(del_passive_rule)

        load_passive_apps()

        # --- Пасивно активні категорії ---
        passive_cat_group = QGroupBox("Пасивно активні категорії")
        passive_cat_layout = QHBoxLayout(passive_cat_group)

        self.chk_media_passive = QCheckBox("media")
        cats = self.settings_idle.get("passive_allowed_categories", [])
        self.chk_media_passive.setChecked("media" in cats)

        btn_save_cats = QPushButton("Зберегти")

        def save_passive_cats():
            val = []
            if self.chk_media_passive.isChecked():
                val.append("media")
            self.settings_idle.set("passive_allowed_categories", val)

        btn_save_cats.clicked.connect(save_passive_cats)

        passive_cat_layout.addWidget(self.chk_media_passive)
        passive_cat_layout.addWidget(btn_save_cats)
        passive_cat_layout.addStretch()

        right_col.addWidget(passive_cat_group)
        right_col.addStretch()

        # --- ініціалізація даних ---
        self.load_app_category_rules()
        self.load_toast_settings_ui()
        self.load_ai_settings_ui()
        self.load_profiles_ui()
        self.load_weekly_schedule_ui()
        self.apply_profile_for_today()  # автоматичний вибір профілю за поточним днем

    # ---------------- Idle / AFK ----------------
    def _save_idle_settings(self):
        idle_timeout = int(self.spin_idle.value())
        break_min_visible = int(self.spin_break_min.value())
        self.settings_idle.set("idle_timeout_sec", idle_timeout)
        self.settings_idle.set("break_min_visible_sec", break_min_visible)

    # ---------------- Профілі лімітів ----------------
    def load_profiles_ui(self):
        if not hasattr(self.repo, "list_profiles"):
            self.profile_combo.clear()
            self.profile_combo.addItem("standard")
            self.profile_combo.setEnabled(False)
            self.btn_profile_new.setEnabled(False)
            self.btn_profile_rename.setEnabled(False)
            self.btn_profile_delete.setEnabled(False)

            limits = self.repo.get_all_limits()
            self._apply_limits_to_ui(limits)
            return

        profiles = self.repo.list_profiles()
        if not profiles:
            profiles = ["standard"]

        active = (
            self.repo.get_active_profile_name()
            if hasattr(self.repo, "get_active_profile_name")
            else profiles[0]
        )
        if active not in profiles:
            active = profiles[0]

        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for name in profiles:
            self.profile_combo.addItem(name)
        self.profile_combo.setCurrentText(active)
        self.profile_combo.blockSignals(False)

        limits = (
            self.repo.get_limits_for_profile(active)
            if hasattr(self.repo, "get_limits_for_profile")
            else self.repo.get_all_limits()
        )
        self._apply_limits_to_ui(limits)

    def on_profile_changed(self, name: str):
        if not name:
            return
        if hasattr(self.repo, "get_limits_for_profile"):
            limits = self.repo.get_limits_for_profile(name)
        else:
            limits = self.repo.get_all_limits()
        self._apply_limits_to_ui(limits)
        if hasattr(self.repo, "set_active_profile"):
            try:
                self.repo.set_active_profile(name)
            except Exception:
                pass

    def on_profile_new(self):
        if not hasattr(self.repo, "create_profile"):
            return
        from PyQt6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "Новий профіль", "Назва профілю:")
        if not ok or not name.strip():
            return
        base = self.profile_combo.currentText().strip() or None
        try:
            self.repo.create_profile(name.strip(), base=base)
        except Exception:
            return
        self.load_profiles_ui()
        self.load_weekly_schedule_ui()

    def on_profile_rename(self):
        if not hasattr(self.repo, "rename_profile"):
            return
        from PyQt6.QtWidgets import QInputDialog

        old = self.profile_combo.currentText().strip()
        if not old:
            return
        new, ok = QInputDialog.getText(
            self, "Перейменування профілю", f"Нова назва профілю «{old}»:"
        )
        if not ok or not new.strip():
            return
        try:
            self.repo.rename_profile(old, new.strip())
        except Exception:
            return
        self.load_profiles_ui()
        self.load_weekly_schedule_ui()

    def on_profile_delete(self):
        if not hasattr(self.repo, "delete_profile"):
            return
        current = self.profile_combo.currentText().strip()
        if not current:
            return
        try:
            self.repo.delete_profile(current)
        except Exception:
            return
        self.load_profiles_ui()
        self.load_weekly_schedule_ui()

    def _apply_limits_to_ui(self, limits: Dict[str, dict]):
        for cat, row in self._rows.items():
            cfg = limits.get(cat, {})
            enabled = bool(cfg.get("enabled"))
            minutes = int(cfg.get("limit_minutes") or 0)
            row["chk"].setChecked(enabled)
            row["spin"].setValue(minutes)

    # ---------------- Автовибір профілю за розкладом ----------------
    def apply_profile_for_today(self):
        """
        Автоматично вибирає профіль згідно з розкладом для поточного дня тижня
        і оновлює UI.
        """
        if not hasattr(self.repo, "get_weekly_schedule") or not hasattr(
            self.repo, "set_active_profile"
        ):
            return

        try:
            schedule = self.repo.get_weekly_schedule()

            weekday_idx = datetime.now().weekday()
            weekday_key = self._weekday_keys[weekday_idx]
            profile = schedule.get(weekday_key)
            if not profile:
                return

            self.repo.set_active_profile(profile)
  
            self.load_profiles_ui()
        except Exception:

            return

    # ---------------- Правила застосунків ----------------
    def load_app_category_rules(self):
        self.table_apps.setRowCount(0)
        for rule in self.app_repo.get_rules():
            row = self.table_apps.rowCount()
            self.table_apps.insertRow(row)

            self.table_apps.setItem(row, 0, QTableWidgetItem(rule["exe"]))
            self.table_apps.setItem(row, 1, QTableWidgetItem(rule["title_contains"]))

            combo = QComboBox()
            combo.addItems(CATEGORIES)
            combo.setCurrentText(rule.get("category", "other"))
            self.table_apps.setCellWidget(row, 2, combo)

    def on_add_app_rule(self):
        row = self.table_apps.rowCount()
        self.table_apps.insertRow(row)
        self.table_apps.setItem(row, 0, QTableWidgetItem(""))
        self.table_apps.setItem(row, 1, QTableWidgetItem(""))
        combo = QComboBox()
        combo.addItems(CATEGORIES)
        self.table_apps.setCellWidget(row, 2, combo)

    def on_delete_app_rule(self):
        r = self.table_apps.currentRow()
        if r >= 0:
            self.table_apps.removeRow(r)

    def save_app_category_rules(self):
        rules = []
        for r in range(self.table_apps.rowCount()):
            exe_item = self.table_apps.item(r, 0)
            title_item = self.table_apps.item(r, 1)
            if not exe_item:
                continue
            exe = exe_item.text().strip()
            title = title_item.text().strip() if title_item else ""
            combo = self.table_apps.cellWidget(r, 2)
            cat = combo.currentText() if isinstance(combo, QComboBox) else "other"

            if exe:
                rules.append(
                    {"exe": exe, "title_contains": title, "category": cat}
                )

        self.app_repo.set_rules(rules)

    def on_apply_app_rules(self):
        self.save_app_category_rules()

    # ---------------- Збереження лімітів ----------------
    def save_limits(self):
        limits: Dict[str, dict] = {}
        for cat, row in self._rows.items():
            limits[cat] = {
                "enabled": row["chk"].isChecked(),
                "limit_minutes": row["spin"].value(),
            }

        profile_name = self.profile_combo.currentText().strip() or None
        if hasattr(self.repo, "save_limits_for_profile") and profile_name:
            try:
                self.repo.save_limits_for_profile(profile_name, limits)
                return
            except Exception:
                pass

        if hasattr(self.repo, "save_limits"):
            try:
                self.repo.save_limits(limits)
                return
            except Exception:
                pass
        if hasattr(self.repo, "set_limit"):
            for cat, cfg in limits.items():
                self.repo.set_limit(
                    cat,
                    int(cfg["limit_minutes"]),
                    bool(cfg["enabled"]),
                )

    # ---------------- Розклад профілів ----------------
    def load_weekly_schedule_ui(self):
        if not hasattr(self.repo, "get_weekly_schedule"):
            return

        profiles = (
            self.repo.list_profiles()
            if hasattr(self.repo, "list_profiles")
            else []
        )
        if not profiles:
            profiles = [self.profile_combo.currentText() or "standard"]

        schedule = self.repo.get_weekly_schedule()

        for key, combo in self._weekday_profile_combos.items():
            combo.blockSignals(True)
            combo.clear()
            for name in profiles:
                combo.addItem(name)
            prof = schedule.get(key) or profiles[0]
            if prof in profiles:
                combo.setCurrentText(prof)
            combo.blockSignals(False)

    def save_weekly_schedule_ui(self):
        if not hasattr(self.repo, "save_weekly_schedule"):
            return
        schedule: Dict[str, str] = {}
        for key, combo in self._weekday_profile_combos.items():
            name = combo.currentText().strip()
            if name:
                schedule[key] = name
        try:
            self.repo.save_weekly_schedule(schedule)
        except Exception:
            pass

    # ---------------- Тости ----------------
    def load_toast_settings_ui(self):
        cfg = load_toast_settings()

        self.toast_duration_spin.setValue(cfg["duration_ms"] // 1000)

        position_label = next(
            (
                lbl
                for lbl, code in self._toast_position_map.items()
                if code == cfg["position"]
            ),
            "Нижній правий кут",
        )
        self.toast_position_combo.setCurrentText(position_label)

        self.toast_cooldown_spin.setValue(cfg["cooldown_minutes"])
        self.toast_warn_checkbox.setChecked(cfg["show_warning"])
        self.toast_critical_checkbox.setChecked(cfg["show_critical"])
        self.toast_sound_checkbox.setChecked(cfg["sound_enabled"])

    def save_toast_settings_ui(self):
        label = self.toast_position_combo.currentText()
        cfg = {
            "duration_ms": self.toast_duration_spin.value() * 1000,
            "position": self._toast_position_map[label],
            "cooldown_minutes": self.toast_cooldown_spin.value(),
            "show_warning": self.toast_warn_checkbox.isChecked(),
            "show_critical": self.toast_critical_checkbox.isChecked(),
            "sound_enabled": self.toast_sound_checkbox.isChecked(),
        }
        save_toast_settings(cfg)

    # ---------------- AI-налаштування ----------------
    def load_ai_settings_ui(self):
        cfg = load_ai_settings()
        mode = str(cfg.get("mode", "hybrid")) or "hybrid"
        use_history = bool(cfg.get("use_history", True))

        current_label = None
        for lbl, code in self._ai_mode_map.items():
            if code == mode:
                current_label = lbl
                break
        if current_label is None:
            current_label = "Комбінований (правила + AI + історія)"

        self.ai_mode_combo.setCurrentText(current_label)
        self.ai_history_checkbox.setChecked(use_history)

    def save_ai_settings_ui(self):
        label = self.ai_mode_combo.currentText()
        mode = self._ai_mode_map.get(label, "hybrid")
        use_history = self.ai_history_checkbox.isChecked()

        cfg = {"mode": mode, "use_history": use_history}
        save_ai_settings(cfg)
