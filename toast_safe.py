# core/toast_safe.py

from typing import List, Optional, Dict, Any

from core.fullscreen_detector import is_fullscreen_application
from ui.components.toast import Toast


class ToastSafeManager:


    def __init__(self) -> None:
        # Черга відкладених тостів (коли fullscreen)
        self.queue: List[Dict[str, Any]] = []
        # Уже показані активні тости
        self.active_toasts: List[Toast] = []

    # -----------------------------------------------------------
    # Публічний метод: показати тост
    # -----------------------------------------------------------
    def show_toast_safe(
        self,
        anchor,
        text: str,
        level: str,
        duration: int,
        index: int,
    ) -> Optional[Toast]:

        # Якщо зараз повноекранний застосунок (гра) — не показуємо, тільки кешуємо
        if is_fullscreen_application():
            self.queue.append(
                {
                    "anchor": anchor,
                    "text": text,
                    "level": level,
                    "duration": duration,
                }
            )
            return None

        # Якщо fullscreen немає — показуємо негайно
        return self._show_single_toast(anchor, text, level, duration, index)

    # -----------------------------------------------------------
    # Внутрішній метод: показ одного тоста
    # -----------------------------------------------------------
    def _show_single_toast(
        self,
        anchor,
        text: str,
        level: str,
        duration: int,
        index: int,
    ) -> Toast:
        toast = Toast(anchor, text, level, duration, index)

        def _on_closed(_):
            if toast in self.active_toasts:
                self.active_toasts.remove(toast)

        toast.closed.connect(_on_closed)
        toast.show()
        self.active_toasts.append(toast)
        return toast

    # -----------------------------------------------------------
    # Викликається з MainWindow періодично (таймер 5 с)
    # -----------------------------------------------------------
    def update(self, anchor) -> None:

        if not self.queue:
            return

        if is_fullscreen_application():
            return


        while self.queue:
            data = self.queue.pop(0)
            self._show_single_toast(
                anchor=anchor,
                text=data["text"],
                level=data["level"],
                duration=data["duration"],
                index=len(self.active_toasts),
            )
