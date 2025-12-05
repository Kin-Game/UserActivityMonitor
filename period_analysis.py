import json
from core.recommendations import RecommendationService
from config.prompts import PERIOD_ANALYSIS_PROMPT


class PeriodAnalysisService:


    def __init__(self):
        self.rec = RecommendationService()

    def build_period_report(self, data: dict) -> str:


        # Формуємо JSON-пакет даних для LLM
        payload = {
            "period": data.get("period"),
            "categories": data.get("cat_minutes", {}),
            "apps": [
                {
                    "app": app,
                    "title": title,
                    "category": cat,
                    "minutes": minutes
                }
                for (app, title, cat, minutes) in data.get("apps", [])
            ],
            "daily_totals": data.get("daily_totals", {}),
            "heatmap": data.get("heatmap_data", {}),
        }

        json_block = json.dumps(payload, ensure_ascii=False, indent=2)

        # Пробуємо викликати AI через існуючу рекомендаторку
        response = self.rec._try_generate_ai_recommendations(
            PERIOD_ANALYSIS_PROMPT.format(data=json_block)
        )

        if response and response.strip():
            return response.strip()

        # Якщо Ollama недоступна → fallback
        return self._fallback_report(data)

    def _fallback_report(self, data: dict) -> str:
        cats = data.get("cat_minutes", {})
        apps = data.get("apps", [])
        start, end = data.get("period", ("?", "?"))

        total = sum(cats.values()) if cats else 0
        avg = total / max(1, len(data.get("daily_totals", {})))

        top_cat = max(cats, key=cats.get) if cats else "немає даних"
        top_app = apps[0][0] if apps else "немає даних"

        return (
            f"AI недоступний, але ось короткий аналіз за період {start} — {end}:\n\n"
            f"• Загальний час активності: {total:.1f} хв\n"
            f"• Середня активність на день: {avg:.1f} хв\n"
            f"• Найбільше часу витрачено на категорію: {top_cat}\n"
            f"• Топ застосунок: {top_app}\n"
            f"• Днів у вибірці: {len(data.get('daily_totals', {}))}\n"
        )
