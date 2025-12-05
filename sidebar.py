from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSpacerItem, QSizePolicy


class Sidebar(QWidget):
    """
    Мінімалістичне вертикальне меню з трьома кнопками:
    Dashboard / Statistics / Settings.
    Дає сигнал page_selected(index).
    """

    page_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedWidth(80)  # компактна панель

        self._buttons: list[QPushButton] = []

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Кнопки меню
        self.btn_dashboard = self._create_button("🏠", "Dashboard", 0)
        self.btn_stats = self._create_button("📊", "Statistics", 1)
        self.btn_settings = self._create_button("⚙", "Settings", 2)

        layout.addWidget(self.btn_dashboard)
        layout.addWidget(self.btn_stats)
        layout.addWidget(self.btn_settings)

        # Роздільник, щоб кнопки були зверху
        layout.addSpacerItem(QSpacerItem(
            0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        ))

        self.setLayout(layout)

        # За замовчуванням активний Dashboard
        self.set_current_index(0)

    def _create_button(self, text: str, tooltip: str, index: int) -> QPushButton:
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self._on_button_clicked(index))
        btn.setMinimumHeight(40)

        self._buttons.append(btn)
        return btn

    def _on_button_clicked(self, index: int):
        self.set_current_index(index)
        self.page_selected.emit(index)

    def set_current_index(self, index: int):
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)
