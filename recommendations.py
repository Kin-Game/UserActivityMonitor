from typing import Dict, List
import subprocess

from core.analytics import AnalyticsService
from storage.limits_repo import CategoryLimitsRepository, CATEGORIES
from config.prompts import RECOMMEND_PROMPT
from config.settings import OLLAMA_EXECUTABLE, OLLAMA_MODEL


class RecommendationService:


    def __init__(self):
        self.analytics = AnalyticsService()
        self.limits_repo = CategoryLimitsRepository()
        self.ollama_exec = OLLAMA_EXECUTABLE
        self.ollama_model = OLLAMA_MODEL

    # --------- допоміжні форматери ---------

    @staticmethod
    def _format_minutes_full(minutes: float) -> str:

        total_sec = int(round(minutes * 60))
        if total_sec < 0:
            total_sec = 0
        h = total_sec // 3600
        m = (total_sec % 3600) // 60
        s = total_sec % 60

        parts: List[str] = []
        if h > 0:
            parts.append(f"{h} год")
        if m > 0 or h > 0:
            parts.append(f"{m} хв")
        parts.append(f"{s} с")
        return " ".join(parts)

    # --------- основний публічний метод для дашборду ---------

    def build_today_recommendations(self) -> str:

        used_min: Dict[str, float] = self.analytics.get_today_category_minutes()
        limits = self.limits_repo.get_all_limits()

        # якщо взагалі немає даних
        if not used_min and not limits:
            return (
                "На сьогодні поки що недостатньо даних для повноцінного аналізу.\n"
                "Запусти моніторинг, попрацюй хоча б 30–40 хвилин у різних застосунках, "
                "а потім онови рекомендації."
            )

        # людські назви категорій (для тексту)
        human_names: Dict[str, str] = {
            "work": "робота",
            "games": "ігри",
            "media": "медіа",
            "browsing": "серфінг",
            "communication": "спілкування",
            "social": "соціальні мережі",
            "education": "навчання",
            "other": "інше",
        }

        summary_lines: List[str] = []
        rule_messages: List[str] = []

        # проходимося по всіх категоріях у фіксованому порядку
        for cat in CATEGORIES:
            limit_cfg = limits.get(cat, {})
            limit_min = float(limit_cfg.get("limit_minutes") or 0)
            enabled = bool(limit_cfg.get("enabled"))

            used = float(used_min.get(cat, 0.0))
            # якщо категорія і не використовується, і не має ліміту – пропускаємо
            if used <= 0 and not enabled:
                continue

            cat_name = human_names.get(cat, cat)
            used_str = self._format_minutes_full(used) if used > 0 else "0 с"

            # ліміт не вмикали – просто констатуємо факт використання
            if not enabled or limit_min <= 0:
                summary_lines.append(
                    f"Категорія «{cat_name}»: використано {used_str}, ліміт не встановлено."
                )
                continue

            limit_str = self._format_minutes_full(limit_min)
            ratio = used / limit_min if limit_min > 0 else 0.0

            # категорія взагалі не використовувалась, але ліміт є
            if used <= 0:
                summary_lines.append(
                    f"Категорія «{cat_name}»: сьогодні ще не використовувалась, ліміт {limit_str}."
                )
                continue

            # Перевищення ліміту
            if ratio >= 1.0:
                over_min = used - limit_min
                over_str = self._format_minutes_full(over_min)
                summary_lines.append(
                    f"Категорія «{cat_name}»: перевищено ліміт {limit_str}, фактично {used_str} "
                    f"(перевищення приблизно на {over_str})."
                )
                rule_messages.append(
                    f"У категорії «{cat_name}» ліміт уже перевищено приблизно на {over_str}."
                )
            # Наближення до ліміту (80%+)
            elif ratio >= 0.8:
                remain_min = max(0.0, limit_min - used)
                remain_str = self._format_minutes_full(remain_min)
                summary_lines.append(
                    f"Категорія «{cat_name}»: використано {used_str} з ліміту {limit_str} "
                    f"(залишилось близько {remain_str} до межі)."
                )
                rule_messages.append(
                    f"Категорія «{cat_name}» наближається до ліміту: {used_str} з {limit_str}. "
                    f"Залишилось орієнтовно {remain_str}. "
                    f"Можна поступово планувати перехід до більш продуктивної активності."
                )
            # Все в нормі
            else:
                summary_lines.append(
                    f"Категорія «{cat_name}»: {used_str} при ліміті {limit_str}, поки в межах норми."
                )

        # якщо взагалі нічого не назбирали – всі ліміти в нормі і даних мало
        if not summary_lines:
            base_text = (
                "На сьогодні всі активності знаходяться в межах встановлених лімітів.\n"
                "Час розподілено доволі збалансовано – можна продовжувати працювати в такому режимі."
            )
            # тут немає сенсу ганяти LLM – просто повертаємо текст
            return base_text

        summary_text = "\n".join(summary_lines)
        rule_text = "\n\n".join(rule_messages) if rule_messages else summary_text

        # Для дашборду формуємо промпт на основі RECOMMEND_PROMPT
        prompt = RECOMMEND_PROMPT.format(summary=summary_text)

        # Підключаємо LLM. Якщо все ОК – повернемо AI-версію,
        # якщо ні – fallback на rule_text.
        ai_text = self._try_generate_ai_recommendations(prompt)
        return ai_text or rule_text

    # --------- LLM-шар ---------

    def _try_generate_ai_recommendations(self, prompt: str) -> str | None:

        if not self.ollama_exec or not self.ollama_model:
            return None

        try:
            result = subprocess.run(
                [self.ollama_exec, "run", self.ollama_model],
                input=prompt.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=25,
            )
        except Exception:
            return None

        if result.returncode != 0:
            return None

        stdout = result.stdout.decode("utf-8", errors="ignore").strip()
        if not stdout:
            return None

        # Довжина звіту обмежується самим промптом / моделлю.
        return stdout
