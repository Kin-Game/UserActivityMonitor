# ui/components/trend_chart.py
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.ticker import FuncFormatter
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from datetime import datetime

from core.utils import format_duration_human


class TrendChart(QWidget):

    CATEGORY_COLORS = {
        "робота": "#4e9cff",
        "ігри": "#ffcc00",
        "медіа": "#a3ff4a",
        "спілкування": "#d240ff",
        "серфінг": "#bbbbbb",
        "соцмережі": "#ff6a6a",
        "навчання": "#baffc9",
        "інше": "#888888",
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        self.fig, self.ax = plt.subplots(figsize=(4, 3), dpi=100)
        self.canvas = FigureCanvas(self.fig)

        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.ax.set_facecolor("#1e1e1e")
        self.fig.patch.set_facecolor("#1e1e1e")

        # Форматування підписів по осі Y (значення в хвилинах → людиночитний формат)
        self.ax.yaxis.set_major_formatter(FuncFormatter(self._format_ytick))
        self.ax.set_ylabel("Час")

    def plot(self, daily_totals: dict):
        """
        daily_totals = {
            "2025-11-14": {"робота": 12.3, "ігри": 1.2, ...},
            "2025-11-15": {...},
            ...
        }
        """

        self.ax.clear()
        self.ax.set_facecolor("#1e1e1e")

        # Після clear() потрібно знову повісити форматер та підпис осі
        self.ax.yaxis.set_major_formatter(FuncFormatter(self._format_ytick))
        self.ax.set_ylabel("Час")

        if not daily_totals:
            self.ax.text(
                0.5,
                0.5,
                "Немає даних для побудови графіка",
                color="white",
                ha="center",
                va="center",
            )
            self.canvas.draw()
            return

        # Сортуємо дні
        days = sorted(daily_totals.keys(), key=lambda d: datetime.strptime(d, "%Y-%m-%d"))

        categories = set()
        for d in daily_totals.values():
            categories.update(d.keys())
        categories = sorted(categories)

        # Для кожної категорії будуємо лінію
        for cat in categories:
            values = []
            for day in days:
                values.append(daily_totals[day].get(cat, 0))

            self.ax.plot(
                days,
                values,
                label=cat,
                linewidth=2,
                marker="o",
                color=self.CATEGORY_COLORS.get(cat, "#cccccc"),
            )

        self.ax.set_title("Динаміка активності по днях", color="white")
        self.ax.tick_params(axis="x", rotation=45, colors="white")
        self.ax.tick_params(axis="y", colors="white")
        self.ax.legend(facecolor="#303030", labelcolor="white")

        self.fig.tight_layout()
        self.canvas.draw()

    def _format_ytick(self, value, pos):
        """
        value — хвилини (float) по осі Y.
        Повертаємо людиночитний формат: '45 с', '3 хв 10 с', '2 год 15 хв'.
        """
        seconds = int(round(value * 60))
        if seconds <= 0:
            return "0"
        return format_duration_human(seconds)
