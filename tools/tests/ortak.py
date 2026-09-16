"""Testlerin ortak yardimcilari.

Testler GERCEK ekrani okuyor: dummy pencere baska bir pencere tarafindan
ortulurse olcumler o pencereyi okur ve test sahte sebeplerle duser. Bu yuzden
dummy hem "her zaman ustte" olmali hem de gercekten on plana alinmali.
"""

import time


def pump(app, seconds):
    """Qt olay dongusunu isletirken bekle."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def force_foreground(widget, app, tries=6) -> bool:
    """Pencereyi gercekten on plana al ve dogrula.

    Windows, on planda olmayan bir surecin SetForegroundWindow cagrisini
    reddeder (alt surecte calisan testlerde tam olarak bu olur). Standart
    cozum: on plandaki pencerenin girdi kuyruguna gecici olarak baglanmak.
    """
    try:
        import win32api
        import win32con
        import win32gui
        import win32process
    except Exception:
        widget.raise_()
        widget.activateWindow()
        pump(app, 0.4)
        return True

    hwnd = int(widget.winId())
    for _ in range(tries):
        widget.raise_()
        widget.activateWindow()
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            foreground = win32gui.GetForegroundWindow()
            target = win32process.GetWindowThreadProcessId(foreground)[0]
            own = win32api.GetCurrentThreadId()
            attached = False
            if target and target != own:
                attached = bool(win32process.AttachThreadInput(target, own, True))
            try:
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
            finally:
                if attached:
                    win32process.AttachThreadInput(target, own, False)
        except Exception:
            pass
        pump(app, 0.35)
        if win32gui.GetForegroundWindow() == hwnd:
            return True
    return False
