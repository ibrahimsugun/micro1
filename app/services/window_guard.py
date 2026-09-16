"""Oyun penceresi denetimi.

Yalnız GUI thread'inde QTimer ile çalışır (kural #5).

NORMAL MOD: Ön plandaki pencerenin BAŞLIĞI ayarlı başlıkla eşleşmezse
app_state.game_focused temizlenir; ilk master başlatmasında başlık boşsa ön
plandaki pencereden otomatik yakalanır.

ARKA PLAN MODU: Pencere HWND ile bulunup izlenir. Kapı artık "ön planda mı"
değil, "pencere yaşıyor ve YAKALANABILIYOR mu" sorusudur; böylece oyun başka
pencerelerin arkasındayken de modüller çalışmaya devam eder. Pencere kapanıp
yeniden açılırsa HWND yeniden çözülür (kendini onarır).
"""

import os
import time

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from . import window_capture

try:
    import win32gui
    import win32process

    WIN32GUI_AVAILABLE = True
except Exception:                                    # pragma: no cover
    WIN32GUI_AVAILABLE = False


def foreground_title() -> str:
    if not WIN32GUI_AVAILABLE:
        return ""
    try:
        return win32gui.GetWindowText(win32gui.GetForegroundWindow()) or ""
    except Exception:
        return ""


def foreground_is_own() -> bool:
    """Ön plandaki pencere BİZE mi ait?

    Master'a basıldığı anda ön plandaki pencere programın kendisidir. Başlığı
    oyun başlığı sanılırsa panel odaktayken "oyun odakta" zannedilir ve
    modüller yanlış yere tuş göndermeye başlar.
    """
    if not WIN32GUI_AVAILABLE:
        return False
    try:
        _thread, pid = win32process.GetWindowThreadProcessId(
            win32gui.GetForegroundWindow()
        )
        return pid == os.getpid()
    except Exception:
        return False


# Yakalamanın "taze" sayılacağı üst sınır: tarayıcı 10 FPS ürettiği için üç
# kaçan kare hâlâ geçici bir aksama olabilir; bunun üstü gerçek bir sorundur.
CAPTURE_STALE_SECONDS = 1.5


class WindowGuard(QObject):
    focusChanged = pyqtSignal(bool)
    titleCaptured = pyqtSignal(str)
    hwndChanged = pyqtSignal(object)          # int | None
    embedStatusChanged = pyqtSignal(str)      # "" = sorun yok

    def __init__(self, app_state, scanner=None, parent=None):
        super().__init__(parent)
        self._state = app_state
        self._scanner = scanner
        self._title = ""
        self._last = None
        self._embed = False
        self._hwnd = None
        self._status = None
        # Kendi pencerelerimiz hedef sanılmasın. Testler bu değeri 0 yaparak
        # aynı süreçte açılan sahte oyun penceresini bulabilir.
        self._own_pid = os.getpid()
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._timer.start()
        self._tick()

    def stop(self):
        self._timer.stop()

    def set_title(self, title: str):
        self._title = (title or "").strip()
        self._last = None
        self._set_hwnd(None)               # başlık değişti: yeniden çöz
        self._tick()

    def title(self) -> str:
        return self._title

    # ------------------------------------------------------------ arka plan
    def set_embed_mode(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self._embed:
            return
        self._embed = enabled
        self._last = None
        self._status = None
        if not enabled:
            self._set_hwnd(None)
        self._tick()

    def embed_mode(self) -> bool:
        return self._embed

    def hwnd(self):
        return self._hwnd

    def _set_hwnd(self, hwnd):
        hwnd = int(hwnd) if hwnd else None
        if hwnd != self._hwnd:
            self._hwnd = hwnd
            self.hwndChanged.emit(hwnd)

    def _set_status(self, text: str):
        if text != self._status:
            self._status = text
            self.embedStatusChanged.emit(text)

    def capture_current(self) -> str:
        """Ön plandaki pencerenin başlığını al.

        Kendi pencerelerimiz ATLANIR: aksi halde master'a basıldığı anda
        panelin kendi başlığı "oyun penceresi" olarak kaydedilirdi.
        """
        if foreground_is_own():
            return ""
        title = foreground_title().strip()
        if title:
            self._title = title
            self.titleCaptured.emit(title)
        return title

    def _tick(self):
        if self._embed:
            ready = self._tick_embed()
        else:
            if not self._title or foreground_is_own():
                # Kendi panelimiz öndeyken oyun odakta sayılmaz.
                ready = False
            else:
                current = foreground_title()
                ready = self._title.lower() in current.lower()
        if ready:
            self._state.game_focused.set()
        else:
            self._state.game_focused.clear()
        if ready != self._last:
            self._last = ready
            self.focusChanged.emit(ready)

    def _tick_embed(self) -> bool:
        """Kapı: pencere yaşıyor ve yakalanabiliyor mu? (ön plan ŞARTI YOK)"""
        if not self._title:
            self._set_hwnd(None)
            self._set_status("Oyun penceresi başlığı boş.")
            return False

        hwnd = self._hwnd
        if hwnd and not window_capture.is_window_usable(hwnd):
            hwnd = None
        if not hwnd:
            # Kapanma / yeniden açılma / HWND değişimi burada kendini onarır.
            hwnd = window_capture.find_game_window(self._title, self._own_pid)
        self._set_hwnd(hwnd)

        if not hwnd:
            self._set_status("Oyun penceresi bulunamadı: '{}'".format(self._title))
            return False

        if window_capture.is_window_minimized(hwnd):
            # Simge durumundayken pencerenin çizim yüzeyi yoktur. Odağı
            # ÇALMADAN geri getir; gözetimsiz çalışma bunu gerektiriyor.
            window_capture.restore_no_activate(hwnd)
            self._set_status("Pencere simge durumundaydı, geri getirildi.")
            return False

        if self._scanner is None:
            self._set_status("")
            return True

        age = time.monotonic() - self._scanner.stamp()
        if age > CAPTURE_STALE_SECONDS:
            self._set_status("Görüntü alınamıyor: {}".format(
                self._scanner.last_error or "kare gelmiyor"))
            return False

        self._set_status("")
        return True
