import subprocess
from typing import Dict

from config.prompts import CLASSIFY_PROMPT
from config.settings import OLLAMA_EXECUTABLE, OLLAMA_MODEL
from config.ai_settings import load_ai_settings
from storage.profile_repo import CategoryProfileRepository
from storage.app_category_profile_repo import AppCategoryProfileRepository
from storage.limits_repo import CATEGORIES


ALLOWED_CATEGORIES = {
    "work",
    "games",
    "media",
    "browsing",
    "communication",
    "social",
    "education",
    "other",
}

DEBUG_CLASSIFIER = True


class Classifier:

    # Поріг для історії (min count, min share), коли довіряємо більшості
    HISTORY_MIN_TOTAL = 5
    HISTORY_MIN_SHARE = 0.7

    def __init__(self) -> None:
        self.model = OLLAMA_MODEL
        self.exec_path = OLLAMA_EXECUTABLE
        self.profile_repo = CategoryProfileRepository()
        self.app_profiles = AppCategoryProfileRepository()

        # Завантажуємо налаштування AI
        ai_cfg = load_ai_settings()
        self.mode: str = str(ai_cfg.get("mode", "hybrid")) or "hybrid"
        if self.mode not in {"hybrid", "rules_only", "llm_only"}:
            self.mode = "hybrid"

        self.use_history: bool = bool(ai_cfg.get("use_history", True))

    # --------- Публічний інтерфейс ---------

    def classify(self, app: str, title: str) -> str:

        app = app or ""
        title = title or ""

        # --------- Режим: тільки правила ---------
        if self.mode == "rules_only":
            manual_cat = self.app_profiles.find_match(app, title)
            if manual_cat and manual_cat in CATEGORIES:
                return manual_cat
            return "other"

        # --------- Режим: hybrid або llm_only ---------

        manual_cat = None
        if self.mode == "hybrid":
            manual_cat = self.app_profiles.find_match(app, title)
            if manual_cat and manual_cat in CATEGORIES:
                return manual_cat

        # LLM-класифікація
        llm_cat = self._classify_via_llm(app, title)
        if llm_cat not in CATEGORIES:
            llm_cat = "other"

        # Семантична постобробка (YouTube → media тощо)
        candidate = self._postprocess_semantic(app, title, llm_cat)

        # Історична корекція тільки в режимі hybrid і якщо вона дозволена
        if self.mode == "hybrid" and self.use_history:
            signature = self._make_signature(app, title)
            final = self._apply_history(signature, candidate)
        else:
            final = candidate

        return final

    # --------- Внутрішні методи ---------

    def _classify_via_llm(self, app: str, title: str) -> str:
        prompt = CLASSIFY_PROMPT.format(app=app, title=title)

        if DEBUG_CLASSIFIER:
            print("\n========== CLASSIFIER CALL ==========")
            print(f"Exec:  {self.exec_path}")
            print(f"Model: {self.model}")
            print(f"App:   {app}")
            print(f"Title: {title}")
            print("=====================================")

        try:
            result = subprocess.run(
                [self.exec_path, "run", self.model],
                input=prompt.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
            )
        except Exception as e:
            if DEBUG_CLASSIFIER:
                print(f"[CLASSIFIER] Exception while calling ollama: {e}")
            return "other"

        stdout = result.stdout.decode("utf-8", errors="ignore").strip()
        stderr = result.stderr.decode("utf-8", errors="ignore").strip()

        if DEBUG_CLASSIFIER:
            print("--- OLLAMA RAW STDOUT ---")
            print(stdout if stdout else "<empty>")
            print("--- OLLAMA RAW STDERR ---")
            print(stderr if stderr else "<empty>")
            print(f"Return code: {result.returncode}")

        if result.returncode != 0 or not stdout:
            return "other"

        # Беремо останній непорожній рядок
        lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
        if not lines:
            return "other"

        raw = lines[-1].lower().replace(".", "").strip()
        tokens = [t for t in raw.split() if t]
        candidate = tokens[-1] if tokens else raw

        if candidate not in ALLOWED_CATEGORIES and DEBUG_CLASSIFIER:
            print(f"[CLASSIFIER] Unknown category from LLM '{candidate}', fallback to 'other'")

        return candidate if candidate in ALLOWED_CATEGORIES else "other"

    def _postprocess_semantic(self, app: str, title: str, candidate: str) -> str:

        title_l = (title or "").lower()
        final = candidate

        if "youtube" in title_l and final in {"browsing", "other"}:
            if DEBUG_CLASSIFIER:
                print(f"[CLASSIFIER] Semantic fix: YouTube {candidate} -> media")
            final = "media"

        return final

    def _make_signature(self, app: str, title: str) -> str:

        app_key = (app or "").lower()
        title_l = (title or "").lower()
        key_parts = [app_key]

        keywords: list[str] = []

        semantic_markers = [
            "youtube",
            "binance",
            "airdrop",
            "steam",
            "netflix",
            "discord",
            "telegram",
            "whatsapp",
            "chatgpt",
            "visual studio code",
            "user activity monitor",
            "schedule",
            "розклад",
            "серіал",
            "фільм",
            "курс",
            "лекція",
            "tutorial",
            "docs",
        ]

        for kw in semantic_markers:
            if kw in title_l:
                keywords.append(kw)

        if keywords:
            key_parts.extend(sorted(set(keywords)))

        return "::".join(key_parts)

    def _apply_history(self, signature: str, candidate: str) -> str:

        majority_cat, count, share = self.profile_repo.get_majority(signature)

        if DEBUG_CLASSIFIER:
            print(
                f"[CLASSIFIER] History for {signature}: "
                f"majority={majority_cat}, count={count}, share={share:.2f}"
            )

        final = candidate

        if majority_cat and majority_cat in ALLOWED_CATEGORIES:
            if count >= self.HISTORY_MIN_TOTAL and share >= self.HISTORY_MIN_SHARE:
                if majority_cat != candidate and DEBUG_CLASSIFIER:
                    print(f"[CLASSIFIER] History override: {candidate} -> {majority_cat}")
                final = majority_cat

        return final
