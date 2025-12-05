from __future__ import annotations

from pathlib import Path
import sys


def app_root() -> Path:

    base = getattr(sys, "_MEIPASS", None) 
    if base is not None:
        return Path(base)

    return Path(__file__).resolve().parent.parent


def db_path() -> Path:

    return app_root() / "user_activity.sqlite3"


def data_dir() -> Path:

    return app_root() / "data"

def data_file(name: str) -> Path:

    return data_dir() / name

def logs_dir() -> Path:

    return app_root() / "logs"


def ui_resources_dir() -> Path:

    return app_root() / "ui" / "resources"

def icon_path(name: str) -> Path:

    return ui_resources_dir() / "icons" / name

def ensure_logs_dir() -> Path:

    d = logs_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d
