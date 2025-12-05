import win32gui
import win32con

def _get_foreground_window_info():

    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None, None

    try:
        rect = win32gui.GetWindowRect(hwnd)
        return hwnd, rect
    except Exception:
        return hwnd, None


def is_fullscreen_application() -> bool:


    hwnd, rect = _get_foreground_window_info()
    if not hwnd or not rect:
        return False

    left, top, right, bottom = rect
    w = right - left
    h = bottom - top

    # Розмір робочого столу (primary monitor)
    screen_w = win32gui.GetSystemMetrics(win32con.SM_CXSCREEN)
    screen_h = win32gui.GetSystemMetrics(win32con.SM_CYSCREEN)

    # Якщо фактично на весь екран
    fullscreen_like = (abs(w - screen_w) <= 2) and (abs(h - screen_h) <= 2)

    if not fullscreen_like:
        return False

    # Перевіряємо заголовок (браузери не викидаємо)
    title = win32gui.GetWindowText(hwnd).lower()

    browser_signatures = [
        "chrome", "edge", "mozilla", "firefox",
        "opera", "vivaldi", "safari", "brave"
    ]

    if any(sig in title for sig in browser_signatures):
        return False

    # Перевіряємо клас вікна (деякі плеєри та IDE в fullscreen не викидаємо)
    cls = win32gui.GetClassName(hwnd).lower()

    ignore_classes = [
        "chrome_widgetwin", "applicationframewindow",
        "windows.ui.core.corewindow",
        "multitaskingviewframe", "cabinetwclass"
    ]

    if cls in ignore_classes:
        return False

    return True
