from typing import Dict

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from core.utils import format_duration_human


# Синхронні назви й кольори категорій
CATEGORY_LABELS = {
    "work": "робота",
    "games": "ігри",
    "media": "медіа",
    "browsing": "серфінг",
    "communication": "спілкування",
    "social": "соцмережі",
    "education": "навчання",
    "other": "інше",
}

CATEGORY_COLORS = {
    "work": "#4A90E2",
    "games": "#F5A623",
    "media": "#7ED321",
    "browsing": "#50E3C2",
    "communication": "#BD10E0",
    "social": "#F8E71C",
    "education": "#B8E986",
    "other": "#9B9B9B",
}


class CategoryChartWidget(QWidget):
    """
    Bar-chart "Час за категоріями (сьогодні)".
    Вхідні дані: {category_key: minutes_float}
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.figure = Figure(figsize=(4, 3))
        self.canvas = FigureCanvas(self.figure)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        self.figure.patch.set_facecolor("#202020")

    @staticmethod
    def _format_hms_from_minutes(minutes: float) -> str:
        """
        Форматує тривалість у хвилинах у людиночитний формат через format_duration_human.
        """
        total_seconds = int(round(minutes * 60))
        return format_duration_human(total_seconds)

    def _format_cat_ytick(self, value, pos):
        """
        value — хвилини (float) по осі Y.
        Конвертуємо в секунди і далі в людиночитний формат.
        """
        seconds = int(round(value * 60))
        if seconds <= 0:
            return "0"
        return format_duration_human(seconds)

    def update_data(self, data: Dict[str, float]):
        """
        Оновити графік.
        data: {category_key: minutes}
        """
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor("#202020")

        if not data:
            ax.text(
                0.5,
                0.5,
                "Немає даних за сьогодні",
                ha="center",
                va="center",
                fontsize=9,
                color="#FFFFFF",
                transform=ax.transAxes,
            )
            ax.set_xticks([])
            ax.set_yticks([])
        else:
            # впорядкуємо категорії за ключами, щоб кольори були стабільні
            categories = [k for k in CATEGORY_LABELS.keys() if k in data]
            values = [data.get(cat, 0.0) for cat in categories]
            labels = [CATEGORY_LABELS.get(cat, cat) for cat in categories]
            colors = [CATEGORY_COLORS.get(cat, "#4A90E2") for cat in categories]

            # Малюємо бари
            bars = ax.bar(labels, values, color=colors)

            # Підпис осі Y + форматер (хвилини → людиночитний час)
            ax.yaxis.set_major_formatter(FuncFormatter(self._format_cat_ytick))
            ax.set_ylabel("Час", color="#FFFFFF")

            # Заголовок
            ax.set_title("Час за категоріями (сьогодні)", color="#FFFFFF")

            # X-вісь: підписи горизонтально
            ax.tick_params(axis="x", colors="#FFFFFF", rotation=0)
            ax.tick_params(axis="y", colors="#FFFFFF")
            ax.grid(axis="y", color="#444444", linestyle="--", linewidth=0.5, alpha=0.7)

            # Підписи над стовпчиками у тому ж форматі, що й решта інтерфейсу
            for bar, minutes in zip(bars, values):
                label = self._format_hms_from_minutes(minutes)
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    height,
                    label,
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color="#FFFFFF",
                )

        # Відступи, щоб не обрізати довгі підписи по осі Y
        self.figure.subplots_adjust(left=0.12, right=0.98, top=0.9, bottom=0.18)
        self.canvas.draw_idle()
