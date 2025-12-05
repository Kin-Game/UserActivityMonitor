import subprocess
from config.prompts import RECOMMEND_PROMPT


class Recommender:
    MODEL = "llama3"

    def generate(self, category: str, used_minutes: int, limit: int) -> str:
        prompt = RECOMMEND_PROMPT.format(
            category=category,
            used=used_minutes,
            limit=limit
        )

        try:
            result = subprocess.run(
                ["ollama", "run", self.MODEL],
                input=prompt.encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15
            )
            return result.stdout.decode().strip()

        except Exception:
            return "Take a short break."
