"""Arka plan (pencere yakalama) modu testleri.

Bu test GERCEK TUS/TIK GONDERMEZ; yalnizca pencere bulma, yakalama ve mod
anahtarlamasini dogrular. Kritik iddia: pencere BASKA BIR PENCERE TARAFINDAN
TAMAMEN ORTULUYKEN bile icerigi okunabiliyor.
"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402
from PyQt5.QtCore import QPoint, Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication, QWidget  # noqa: E402

from app.app_state import AppState  # noqa: E402
from app.services import window_capture as wc  # noqa: E402
from app.services.screen_scanner import (  # noqa: E402
    MODE_SCREEN, MODE_WINDOW, ScreenScanner,
)
from app.services.window_guard import WindowGuard  # noqa: E402

from ortak import pump  # noqa: E402

from dummy_game_window import HP_RECT, DummyGameWindow  # noqa: E402

RESULTS = []
TITLE = "Pencere Yakalama Testi"


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("[{}] {}{}".format("PASS" if ok else "FAIL", name,
                             ("  -- " + detail) if detail else ""))


def global_rect(widget, rect):
    """Qt mantiksal dikdortgen -> fiziksel ekran pikseli (kalibrasyon uzayi)."""
    top_left = widget.mapToGlobal(QPoint(rect.x(), rect.y()))
    ratio = widget.devicePixelRatioF()
    return (int(top_left.x() * ratio), int(top_left.y() * ratio),
            int(rect.width() * ratio), int(rect.height() * ratio))


class Cover(QWidget):
    """Hedefi tamamen orten opak pencere: ortulme testinin kendisi."""

    def __init__(self, rect):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint
                         | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowTitle("ORTUCU")
        self.setStyleSheet("background: #0a0a0a;")
        self.setGeometry(*rect)


app = QApplication(sys.argv)

if not wc.WINAPI_AVAILABLE:
    print("Windows API yok; test atlaniyor")
    sys.exit(0)

dummy = DummyGameWindow()
dummy.setWindowTitle(TITLE)
dummy.move(70, 70)
dummy.show()
pump(app, 1.2)

hwnd = int(dummy.winId())

# --------------------------------------------------------------- pencere bulma
# Sahte oyun penceresi AYNI surecte acildigi icin kendi-surec elemesi kapatilir
# (own_pid=0). Elemenin kendisi bir alt kontrolde dogrulaniyor.
found = wc.find_game_window(TITLE, 0)
check("find_game_window basliktan pencereyi buluyor", found == hwnd,
      "bulunan 0x{:X}, beklenen 0x{:X}".format(found or 0, hwnd))

own = wc.find_game_window(TITLE, os.getpid())
check("Kendi surecimizin pencereleri DISLANIYOR", own is None,
      "donen: {}".format(own))

check("Olmayan baslik icin None",
      wc.find_game_window("XyzYokBoyleBirSey", 0) is None)
check("Bos baslik icin None", wc.find_game_window("", 0) is None)

# --------------------------------------------------------------- olcu bilgisi
bounds = wc.window_client_bounds(hwnd)
check("window_client_bounds makul deger veriyor",
      bounds is not None and bounds[2] > 100 and bounds[3] > 100, str(bounds))

metrics = wc.window_metrics(hwnd)
check("window_metrics client ve cizim olcusu veriyor",
      metrics is not None and metrics["client"] == bounds
      and metrics["render_client"][0] > 0, str(metrics and metrics["render_client"]))

check("is_window_alive acik pencere icin True", wc.is_window_alive(hwnd))
check("is_window_minimized acik pencere icin False",
      not wc.is_window_minimized(hwnd))

# --------------------------------------------------------------- yakalama
grabber = wc.WindowGrabber(lambda: hwnd)
frame = None
for _ in range(5):
    frame, origin = grabber.grab()
    pump(app, 0.15)
    if frame is not None:
        break

check("WindowGrabber kare uretiyor", frame is not None,
      grabber.last_error)

if frame is not None:
    check("Kare FIZIKSEL client olcusunde (kalibrasyon uzayi korunuyor)",
          (frame.shape[1], frame.shape[0]) == (bounds[2], bounds[3]),
          "kare {}x{}, client {}x{}".format(
              frame.shape[1], frame.shape[0], bounds[2], bounds[3]))
    check("Origin client'in ekran kosesi", origin == (bounds[0], bounds[1]),
          str(origin))
    check("Kare siyah degil", bool(frame[::8, ::8].any()),
          "ortalama {:.1f}".format(float(frame.mean())))

# HP barinin rengi dogru yerden okunuyor mu? (ekran koordinati -> kare dilimi)
hp_rect = global_rect(dummy.canvas, HP_RECT)
if frame is not None:
    x = hp_rect[0] - origin[0]
    y = hp_rect[1] - origin[1]
    patch = frame[y:y + hp_rect[3], x:x + hp_rect[2]]
    ok = patch.size > 0
    red_dominant = ok and float(patch[:, :, 2].mean()) > float(patch[:, :, 0].mean())
    check("Ekran koordinatli HP dikdortgeni karede DOGRU yerde (kirmizi bar)",
          red_dominant, "patch {}".format(patch.shape if ok else "bos"))

# --------------------------------------------------------------- ORTULME testi
window_rect = wc.window_bounds(hwnd)
ratio = dummy.devicePixelRatioF() or 1.0
cover = Cover((int(window_rect[0] / ratio) - 10, int(window_rect[1] / ratio) - 10,
               int(window_rect[2] / ratio) + 20, int(window_rect[3] / ratio) + 20))
cover.show()
cover.raise_()
pump(app, 1.0)

covered = None
for _ in range(5):
    covered, _origin = grabber.grab()
    pump(app, 0.15)
    if covered is not None:
        break

check("Pencere TAMAMEN ORTULUYKEN kare aliniyor", covered is not None,
      grabber.last_error)
if covered is not None and frame is not None:
    same_size = covered.shape == frame.shape
    difference = (float(np.abs(covered.astype(np.int16)
                               - frame.astype(np.int16)).mean())
                  if same_size else -1.0)
    check("Ortulu kare, ortulmemis kareyle AYNI icerigi tasiyor",
          same_size and difference < 12.0,
          "ortalama fark {:.2f}".format(difference))

cover.close()
pump(app, 0.4)
grabber.close()

# --------------------------------------------------------------- tarayici modu
live_scanner = ScreenScanner(fps=10.0)
live_scanner.set_mode(MODE_WINDOW)
live_scanner.set_target_hwnd(hwnd)
live_scanner.start()
pump(app, 1.5)

scan_frame, stamp, scan_origin = live_scanner.frame()
check("Tarayici PENCERE modunda kare yayinliyor", scan_frame is not None,
      live_scanner.last_error)
check("Tarayici backend adi pencere yakalamayi gosteriyor",
      "Pencere" in live_scanner.backend, live_scanner.backend)

if scan_frame is not None:
    check("Tarayici karesi client olcusunde",
          (scan_frame.shape[1], scan_frame.shape[0]) == (bounds[2], bounds[3]))
    region = live_scanner.region(hp_rect)
    check("scanner.region() ekran koordinatiyla DEGISMEDEN calisiyor",
          region is not None and region.size > 0
          and float(region[:, :, 2].mean()) > float(region[:, :, 0].mean()),
          "bolge {}".format(None if region is None else region.shape))
    check("screen_size() client olcusunu bildiriyor",
          live_scanner.screen_size() == (bounds[2], bounds[3]),
          str(live_scanner.screen_size()))

# --------------------------------------------------------------- kapi (guard)
state = AppState()
guard = WindowGuard(state, scanner=live_scanner)
guard._own_pid = 0                     # sahte oyun ayni surecte
guard.set_title(TITLE)
guard.set_embed_mode(True)
check("WindowGuard arka plan modunda HWND cozuyor", guard.hwnd() == hwnd,
      "0x{:X}".format(guard.hwnd() or 0))
check("Yakalama tazeyken kapi ACIK (on plan sarti YOK)",
      state.game_focused.is_set())

hwnd_changes = []
guard.hwndChanged.connect(lambda value: hwnd_changes.append(value))

live_scanner.stop()
pump(app, 2.0)
guard._tick()
check("Kare gelmeyi kesince kapi KAPANIYOR (bayat goruntu)",
      not state.game_focused.is_set())

# --------------------------------------------------------------- mod geri donus
back = ScreenScanner(fps=10.0)
back.start()
pump(app, 1.2)
screen_frame, _stamp, screen_origin = back.frame()
check("Normal (ekran) mod hala calisiyor", screen_frame is not None,
      back.last_error)
check("Ekran modunda backend MSS/PyAutoGUI",
      "Pencere" not in back.backend, back.backend)
back.stop()

# --------------------------------------------------------------- pencere kapandi
dummy.close()
pump(app, 1.0)
guard._tick()
check("Pencere kapaninca kapi KAPALI kaliyor", not state.game_focused.is_set())
check("Pencere kapaninca HWND temizleniyor", guard.hwnd() is None,
      str(guard.hwnd()))
check("HWND degisimi sinyalle bildiriliyor", None in hwnd_changes,
      str(hwnd_changes))

print("\n" + "=" * 60)
failed = [n for n, ok in RESULTS if not ok]
print("Toplam {} kontrol, {} basarisiz".format(len(RESULTS), len(failed)))
for name in failed:
    print("  BASARISIZ: " + name)
sys.exit(1 if failed else 0)
