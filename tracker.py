from PyQt6.QtCore import QObject
from typing import Tuple
from datetime import datetime
import win32gui
import win32process
import psutil
import ctypes


class ActiveWindowTracker(QObject):


    IDLE_THRESHOLD_SECONDS = 300  # 5 хвилин без активності = idle

    def get_active_window_info(self) -> Tuple[str, str]:
 
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)

        app = "unknown"
        try:
            pid = win32process.GetWindowThreadProcessId(hwnd)[1]
            process = psutil.Process(pid)
            app = process.name()
        except Exception:
            pass

        return app, title

    # ---- Idle detection ----

    class _LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]

    class _RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    def get_idle_time_seconds(self) -> int:

        last_input_info = self._LASTINPUTINFO()
        last_input_info.cbSize = ctypes.sizeof(last_input_info)

        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(last_input_info)):
            millis = ctypes.windll.kernel32.GetTickCount() - last_input_info.dwTime
            return int(millis / 1000)

        return 0

    def is_user_idle(self, timeout_sec=None):

        idle_sec = self.get_idle_time_seconds()

        if timeout_sec is None:
            timeout_sec = self.IDLE_THRESHOLD_SECONDS

        return idle_sec >= timeout_sec
    
    def is_foreground_fullscreen(self) -> bool:

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return False

        rect = self._RECT()
        if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False

        width = rect.right - rect.left
        height = rect.bottom - rect.top

        screen_w = ctypes.windll.user32.GetSystemMetrics(0)
        screen_h = ctypes.windll.user32.GetSystemMetrics(1)

        # Невелика похибка на рамки / панель задач
        return width >= screen_w - 1 and height >= screen_h - 1

