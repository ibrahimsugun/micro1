"""Merkezî ekran tarayıcı: tek thread, tek mss örneği.

Tuzak #1: mss örneği YALNIZ oluşturulduğu thread'te kullanılabilir; bu yüzden
örnek run() içinde yaratılır ve dışarıya asla sızmaz. Modüller ve kalibrasyon
canlı okuması aynı kareyi paylaşır.

İki mod vardır ve dışarıya verdikleri SÖZLEŞME AYNIDIR — (BGR kare, origin):
  * MODE_SCREEN : tüm sanal masaüstü (mss) — varsayılan, eski davranış birebir.
  * MODE_WINDOW : yalnız hedef pencere (arka plan modu). Kare pencerenin CLIENT
    alanıdır, origin de client'ın ekran köşesidir; böylece region() ekran
    koordinatlı kalibrasyon dikdörtgenlerini DEĞİŞMEDEN doğru diliyor ve
    pencere başka pencerelerin arkasındayken bile okuma sürüyor.
"""

import threading
import time

import numpy as np

from ..constants import SCANNER_FPS

MODE_SCREEN = "screen"
MODE_WINDOW = "window"

try:
    import mss

    MSS_AVAILABLE = True
except Exception:                                    # pragma: no cover
    MSS_AVAILABLE = False

try:
    import pyautogui

    PYAUTOGUI_AVAILABLE = True
except Exception:                                    # pragma: no cover
    PYAUTOGUI_AVAILABLE = False


class ScreenScanner:
    """Sanal masaüstünün tamamını periyodik yakalar, BGR dizi yayınlar."""

    def __init__(self, live_status=None, fps: float = SCANNER_FPS):
        self._live = live_status
        self._interval = 1.0 / max(1.0, float(fps))
        self._lock = threading.Lock()
        # Yeni kare yazildiginda bekleyenleri uyandirir (mesgul bekleme yok).
        # Ekran okumasiyla calisan moduller kendi hizlarinda donup ayni kareyi
        # tekrar tekrar okumasin diye kullanilir.
        self._frame_ready = threading.Condition(self._lock)
        self._frame = None          # np.ndarray (H, W, 3) BGR
        self._stamp = 0.0
        self._origin = (0, 0)       # sanal masaüstü sol/üst köşesi
        self._thread = None
        self._stop = threading.Event()
        self.backend = "-"
        self.last_error = ""
        self._fps_value = 0.0
        # Mod ve hedef pencere GUI thread'inden yazılır, tarayıcı thread'inden
        # okunur. Düz atama GIL altında atomiktir; kilide gerek yok. Sayaç
        # değişince grabber tarayıcı thread'inde YENİDEN kurulur (tuzak #1).
        self._mode = MODE_SCREEN
        self._hwnd = None
        self._target_gen = 0

    # ------------------------------------------------------------------ yaşam
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="ScreenScanner", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    # ------------------------------------------------------------------ mod
    def set_mode(self, mode: str):
        """MODE_SCREEN / MODE_WINDOW. Tarayıcı çalışırken de değiştirilebilir."""
        mode = MODE_WINDOW if mode == MODE_WINDOW else MODE_SCREEN
        if mode != self._mode:
            self._mode = mode
            self._target_gen += 1          # grabber'ı yeniden kurdur

    def mode(self) -> str:
        return self._mode

    def set_target_hwnd(self, hwnd):
        """Pencere modunda okunacak HWND. Grabber her karede yeniden okur."""
        self._hwnd = int(hwnd) if hwnd else None

    def target_hwnd(self):
        return self._hwnd

    # ------------------------------------------------------------------ döngü
    def _run(self):
        grab, teardown = self._make_grabber()
        built_gen = self._target_gen
        frames = 0
        window_start = time.monotonic()
        try:
            while not self._stop.is_set():
                cycle_start = time.monotonic()
                if built_gen != self._target_gen:
                    # Mod değişti: eski grabber'ı BU thread'te yık, yenisini
                    # yine BU thread'te kur (mss/GDI nesneleri thread'e bağlı).
                    built_gen = self._target_gen
                    try:
                        teardown()
                    except Exception:
                        pass
                    grab, teardown = self._make_grabber()
                try:
                    frame, origin = grab()
                    if frame is not None:
                        with self._frame_ready:
                            self._frame = frame
                            self._stamp = cycle_start
                            self._origin = origin
                            self._frame_ready.notify_all()
                        self.last_error = ""
                except Exception as exc:
                    self.last_error = str(exc)
                    time.sleep(0.2)

                frames += 1
                now = time.monotonic()
                if now - window_start >= 1.0:
                    self._fps_value = frames / (now - window_start)
                    frames = 0
                    window_start = now
                    if self._live is not None:
                        self._live.set("scanner_fps", round(self._fps_value, 1))

                sleep_for = self._interval - (time.monotonic() - cycle_start)
                if sleep_for > 0:
                    self._stop.wait(sleep_for)
        finally:
            teardown()

    def _make_grabber(self):
        """(grab, teardown) döndürür. MSS başarısızsa PyAutoGUI'ye düşer."""
        if self._mode == MODE_WINDOW:
            from .window_capture import WindowGrabber

            grabber = WindowGrabber(lambda: self._hwnd)

            def grab_window():
                frame, origin = grabber.grab()
                if frame is None:
                    # Kare yayınlanmaz; damga bayatlar ve WindowGuard bunu
                    # "yakalanamıyor" olarak görüp modülleri bekletir.
                    self.last_error = grabber.last_error
                else:
                    variant = grabber.active_mode()
                    if variant:
                        self.backend = "Pencere ({})".format(variant)
                return frame, origin

            self.backend = "Pencere yakalama"
            return grab_window, grabber.close

        if MSS_AVAILABLE:
            try:
                sct = mss.mss()
                monitor = dict(sct.monitors[0])       # tüm ekranlar birleşik
                origin = (monitor["left"], monitor["top"])

                def grab_mss():
                    raw = np.asarray(sct.grab(monitor))
                    return np.ascontiguousarray(raw[:, :, :3]), origin

                grab_mss()                             # ilk kare: gerçek doğrulama
                self.backend = "MSS"
                return grab_mss, sct.close
            except Exception as exc:
                self.last_error = f"MSS kullanılamadı ({exc}); PyAutoGUI'ye geçildi."

        if not PYAUTOGUI_AVAILABLE:
            raise RuntimeError("Ekran yakalama için ne MSS ne PyAutoGUI kullanılabiliyor.")

        def grab_pag():
            shot = np.asarray(pyautogui.screenshot())  # RGB
            return np.ascontiguousarray(shot[:, :, ::-1]), (0, 0)

        self.backend = "PyAutoGUI (yedek)"
        return grab_pag, lambda: None

    # ------------------------------------------------------------------ okuma
    @property
    def fps(self) -> float:
        return self._fps_value

    def frame(self):
        """(kare, zaman damgası, kaynak) — kare asla mutate EDİLMEZ."""
        with self._lock:
            return self._frame, self._stamp, self._origin

    def stamp(self):
        """Şu anki karenin zaman damgası (kareyi kopyalamadan)."""
        with self._lock:
            return self._stamp

    def wait_for_frame(self, since_stamp, timeout=1.0) -> bool:
        """Verilen damgadan FARKLI bir kare gelene kadar bekler.

        Tarayıcı saniyede SCANNER_FPS kare üretiyor; ekran okumasıyla çalışan
        bir modülün daha sık dönmesi aynı kareyi yeniden okuyup aynı kararı
        yeniden vermek demek. Meşgul bekleme yoktur, koşul değişkeni uyandırır.
        Zaman aşımı, tarayıcı durursa modülün kilitlenmesini önler.
        """
        with self._frame_ready:
            if self._stamp != since_stamp:
                return True
            return self._frame_ready.wait_for(
                lambda: self._stamp != since_stamp, timeout
            )

    def region(self, rect):
        """rect = (x, y, w, h) ekran koordinatı → BGR dilim (kopya değil)."""
        if not rect:
            return None
        frame, _, origin = self.frame()
        if frame is None:
            return None
        x, y, w, h = (int(v) for v in rect)
        if w <= 0 or h <= 0:
            return None
        x -= origin[0]
        y -= origin[1]
        fh, fw = frame.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(fw, x + w), min(fh, y + h)
        if x1 <= x0 or y1 <= y0:
            return None
        return frame[y0:y1, x0:x1]

    def screen_size(self):
        frame, _, _ = self.frame()
        if frame is None:
            return (0, 0)
        return (frame.shape[1], frame.shape[0])
