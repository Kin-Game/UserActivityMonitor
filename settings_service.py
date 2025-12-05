from PyQt6.QtCore import QObject, pyqtSignal


class SettingsService(QObject):


    settings_changed = pyqtSignal(dict)

    def __init__(self, repo):
        super().__init__()
        self.repo = repo
        self.cache = repo.all()

        # Значення за замовчуванням
        if "idle_timeout_sec" not in self.cache:
            self.cache["idle_timeout_sec"] = 300  # 5 хв
            self.repo.set("idle_timeout_sec", 300)

        if "passive_allowed_apps" not in self.cache:
            self.cache["passive_allowed_apps"] = ["vlc.exe", "mpv.exe"]
            self.repo.set("passive_allowed_apps", self.cache["passive_allowed_apps"])

        if "passive_allowed_categories" not in self.cache:
            self.cache["passive_allowed_categories"] = ["media"]
            self.repo.set(
                "passive_allowed_categories",
                self.cache["passive_allowed_categories"],
            )

        # Мінімальна тривалість перерви для відображення (с)
        if "break_min_visible_sec" not in self.cache:
            self.cache["break_min_visible_sec"] = 5
            self.repo.set("break_min_visible_sec", 5)

    def get(self, key, default=None):
        return self.cache.get(key, default)

    def set(self, key: str, value):
        self.cache[key] = value
        self.repo.set(key, value)
        self.settings_changed.emit({key: value})
