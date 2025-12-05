from pathlib import Path
import json

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
)

# Спроба підключити winsound (Windows)
try:
    import winsound
except ImportError:
    winsound = None


# ----------------------------------------------------------------------
# Завантаження налаштувань тостів
# ----------------------------------------------------------------------
def _load_toast_config() -> dict:
    """
    Завантажує налаштування тостів із data/notification_settings.json.
    Якщо файл відсутній або битий — повертає дефолтні значення.

    Підтримуються два формати:
    1) Плоский:
        {
          "duration_ms": 6000,
          "position": "bottom-right",
          "sound_enabled": true,
          ...
        }

    2) Вкладений:
        {
          "toast": {
             "duration_ms": ...,
             "position": ...,
             ...
          },
          ...
        }
    """
    path = Path("data/notification_settings.json")

    cfg = {
        "duration_ms": 6000,
        "position": "bottom-right",   # bottom-right | bottom-left | top-right | top-left
        "cooldown_minutes": 5,
        "show_warning": True,
        "show_critical": True,
        "sound_enabled": False,
    }

    try:
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict):
                # Якщо структура типу {"toast": {...}}
                if "toast" in data and isinstance(data["toast"], dict):
                    cfg.update(data["toast"])
                else:
                    # Якщо все лежить у корені файлу
                    cfg.update(data)
    except Exception:
        # Якщо щось не так із файлом – тихо працюємо з дефолтами
        pass

    return cfg


# ----------------------------------------------------------------------
# Клас Toast
# ----------------------------------------------------------------------
class Toast(QWidget):
    """
    Спливаюче повідомлення (toast):
    - відображається як окреме вікно поверх усіх;
    - позиціонується по екрану (а не по вікну програми);
    - стекується одне над одним за індексом;
    - поважає налаштування з data/notification_settings.json.
    """

    closed = pyqtSignal(object)

    def __init__(
        self,
        anchor,             # для сумісності з існуючим кодом, але не використовується для позиції
        text: str,
        level: str = "warning",  # "warning" | "over"
        duration: int = 6000,
        index: int = 0,
    ):
        super().__init__(None)   # top-level window

        self.anchor = anchor     # зберігаємо тільки для сигнатури, але не позиціонуємося по ньому
        self.index = index
        self._cfg = _load_toast_config()
        self._duration_ms = int(self._cfg.get("duration_ms") or duration or 6000)

        # ------------------------------------------------------------------
        # Параметри вікна
        # ------------------------------------------------------------------
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool          # не показувати в таскбарі
        )
        # НЕ використовуємо WA_TranslucentBackground, щоб не провокувати
        # UpdateLayeredWindowIndirect на WinAPI.

        # ------------------------------------------------------------------
        # Кольори / стилі
        # ------------------------------------------------------------------
        if level == "over":
            border_color = "#FF4C4C"
            icon = "⛔"
        else:
            border_color = "#F5A623"
            icon = "⚠"

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        container = QWidget(self)
        container.setObjectName("toastContainer")

        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(14, 10, 14, 10)
        vbox.setSpacing(6)

        hbox = QHBoxLayout()
        hbox.setSpacing(8)

        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet("font-size: 18px;")

        lbl_text = QLabel(text)
        lbl_text.setWordWrap(True)
        lbl_text.setStyleSheet("font-size: 12px; color: white;")

        btn_close = QPushButton("×")
        btn_close.setObjectName("btnClose")
        btn_close.setFixedSize(20, 20)
        btn_close.clicked.connect(self.close)

        hbox.addWidget(lbl_icon)
        hbox.addWidget(lbl_text)
        hbox.addStretch()
        hbox.addWidget(btn_close)

        vbox.addLayout(hbox)
        root_layout.addWidget(container)

        # Обмеження по ширині — щоб не тягнулося на весь екран
        self.setMinimumWidth(260)
        self.setMaximumWidth(420)
        self.adjustSize()

        self.setStyleSheet(
            f"""
            #toastContainer {{
                background-color: #2C2C2C;
                border-radius: 10px;
                border: 2px solid {border_color};
            }}
            #btnClose {{
                background: transparent;
                color: white;
                font-size: 16px;
                border: none;
            }}
            #btnClose:hover {{
                color: #FF6666;
            }}
            """
        )

        # Початкове позиціонування
        self._position()

        # Анімація + звук + автозакриття
        self._fade_in()
        self._play_sound_if_needed()
        QTimer.singleShot(self._duration_ms, self._fade_out)

    # ------------------------------------------------------------------
    # Позиціонування (по екрану)
    # ------------------------------------------------------------------
    def _position(self) -> None:
        """
        Позиціонує тост відносно ЕКРАНА (primary screen), а не вікна програми.
        Враховує index для вертикального стеку.
        """
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return

        rect = screen.availableGeometry()
        self.adjustSize()

        margin_x = 24
        margin_y = 40
        gap = 10

        pos = self._cfg.get("position", "bottom-right")

        if pos == "bottom-left":
            x = rect.left() + margin_x
            y = rect.bottom() - self.height() - (margin_y + self.index * (self.height() + gap))

        elif pos == "top-right":
            x = rect.right() - self.width() - margin_x
            y = rect.top() + (margin_y + self.index * (self.height() + gap))

        elif pos == "top-left":
            x = rect.left() + margin_x
            y = rect.top() + (margin_y + self.index * (self.height() + gap))

        else:  # bottom-right (за замовчуванням)
            x = rect.right() - self.width() - margin_x
            y = rect.bottom() - self.height() - (margin_y + self.index * (self.height() + gap))

        self.move(x, y)

    def reposition(self) -> None:
        """
        Викликається з MainWindow при зміні розміру / перестановці toasts.
        Просто перевираховує позицію за index, але вже по екрану.
        """
        self._position()

    def showEvent(self, event):
        """
        Після відображення ще раз підганяємо позицію,
        коли розмір уже остаточно порахований.
        """
        super().showEvent(event)
        self._position()

    # ------------------------------------------------------------------
    # Звук
    # ------------------------------------------------------------------
    def _play_sound_if_needed(self) -> None:
        if not self._cfg.get("sound_enabled", False):
            return
        if winsound is None:
            return
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Анімації
    # ------------------------------------------------------------------
    def _fade_in(self) -> None:
        self.setWindowOpacity(0.0)
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(300)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.start()

    def _fade_out(self) -> None:
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(400)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self.anim.finished.connect(self.close)
        self.anim.start()

    # ------------------------------------------------------------------
    # Закриття
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        self.closed.emit(self)
        super().closeEvent(event)
