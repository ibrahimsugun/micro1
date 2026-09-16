"""Faz 0 dogrulama araci: pencere yakalama + arka plan girdi probu.

Amac: "hedef pencere BASKA pencerelerin arkasindayken icerigini okuyabiliyor
muyuz?" sorusuna kanit uretmek. Uc yakalama varyanti olculur:

  client  = PrintWindow(PW_CLIENTONLY|PW_RENDERFULLCONTENT)   (tercih edilen)
  window  = PrintWindow(PW_RENDERFULLCONTENT) + client kirpma (yedek)
  bitblt  = BitBlt                                            (taban cizgisi;
            pencere ORTULUYKEN bozulmasi BEKLENIR - kontrol grubu)

--cover ile arac hedef pencerenin uzerine kendi opak penceresini koyar; boylece
ortulme testi elle pencere suruklemeden, otomatik yapilir.

Kullanim:
    python tools/test_window_capture.py --list
    python tools/test_window_capture.py --title "Knight OnLine Client"
    python tools/test_window_capture.py --title "..." --cover
    python tools/test_window_capture.py --title "..." --preview --cover
    python tools/test_window_capture.py --title "..." --post-key A
    python tools/test_window_capture.py --title "..." --post-click 500 400
"""

import argparse
import ctypes
import os
import sys
import time
from ctypes import wintypes


def _set_dpi_awareness():
    """Ana programla ayni fiziksel piksel uzayinda olmak icin sart."""
    try:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


_set_dpi_awareness()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np                                            # noqa: E402
from PyQt5.QtCore import Qt, QTimer                           # noqa: E402
from PyQt5.QtGui import QImage, QPainter                      # noqa: E402
from PyQt5.QtWidgets import QApplication, QWidget             # noqa: E402

from app.constants import KEYCODES                            # noqa: E402
from app.services import window_capture as wc                 # noqa: E402

VARIANTS = (wc.GRAB_CLIENT, wc.GRAB_WINDOW, wc.GRAB_CLIENT0, wc.GRAB_WINDOW0,
            wc.GRAB_BITBLT)


# --------------------------------------------------------------------- yardimci
def describe(hwnd) -> str:
    rect = wc.window_bounds(hwnd)
    client = wc.window_client_bounds(hwnd)
    return (
        "hwnd=0x{:X}  pid={}\n  baslik : {}\n  sinif  : {}\n"
        "  pencere: {}\n  client : {}\n  simge  : {}".format(
            hwnd, wc.window_pid(hwnd), wc.window_title(hwnd), wc.window_class(hwnd),
            rect, client, "EVET" if wc.is_window_minimized(hwnd) else "hayir",
        )
    )


class CoverWindow(QWidget):
    """Hedefi TAMAMEN orten opak pencere - ortulme testinin kendisi."""

    def __init__(self, rect):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint |
                         Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowTitle("ORTUCU")
        self._rect = rect
        self.setStyleSheet("background: #101010;")

    def place(self):
        x, y, w, h = self._rect
        ratio = self.devicePixelRatioF() or 1.0
        self.setGeometry(int(x / ratio), int(y / ratio),
                         int(w / ratio), int(h / ratio))


class PreviewWindow(QWidget):
    """Canli onizleme: yakalanan kare burada gorunur."""

    def __init__(self, hwnd, mode):
        super().__init__()
        self.setWindowTitle("Yakalama onizleme ({})".format(mode))
        self.resize(720, 460)
        self._grabber = wc.WindowGrabber(lambda: hwnd, mode=mode)
        self._image = None
        self._frame = None
        self._info = "bekleniyor..."
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self):
        frame, origin = self._grabber.grab()
        if frame is None:
            self._info = "HATA: {}".format(self._grabber.last_error)
        else:
            self._frame = frame                       # tampon canli kalsin
            height, width = frame.shape[:2]
            self._image = QImage(frame.data, width, height, width * 3,
                                 QImage.Format_BGR888)
            self._info = "{}x{} @ {}  ort={:.1f}  varyant={}".format(
                width, height, origin, float(frame.mean()),
                self._grabber.active_mode(),
            )
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.black)
        if self._image is not None:
            target = self._image.scaled(self.width(), self.height() - 20,
                                        Qt.KeepAspectRatio, Qt.FastTransformation)
            painter.drawImage((self.width() - target.width()) // 2, 0, target)
        painter.setPen(Qt.white)
        painter.drawText(6, self.height() - 6, self._info)

    def closeEvent(self, event):
        self._timer.stop()
        self._grabber.close()
        super().closeEvent(event)


# --------------------------------------------------------------------- olcumler
def measure(hwnd, mode, frames, pump=None):
    grabber = wc.WindowGrabber(lambda: hwnd, mode=mode)
    ok = 0
    means = []
    live_ratio = []
    error = ""
    start = time.monotonic()
    try:
        for _ in range(frames):
            cycle = time.monotonic()
            frame, _origin = grabber.grab()
            if frame is None:
                error = error or grabber.last_error
            else:
                ok += 1
                sample = frame[::4, ::4]
                means.append(float(sample.mean()))
                live_ratio.append(float((sample > 8).mean()))
            if pump is not None:
                pump()
            rest = 0.1 - (time.monotonic() - cycle)
            if rest > 0:
                time.sleep(rest)
    finally:
        grabber.close()
    elapsed = time.monotonic() - start
    return {
        "mode": mode,
        "ok": ok,
        "total": frames,
        "fps": frames / elapsed if elapsed > 0 else 0.0,
        "mean": sum(means) / len(means) if means else 0.0,
        "live": sum(live_ratio) / len(live_ratio) if live_ratio else 0.0,
        "error": error,
    }


def print_report(title, rows):
    print("\n=== {} ===".format(title))
    print("  {:<8} {:>7} {:>7} {:>9} {:>9}   {}".format(
        "varyant", "basari", "fps", "ort.piksel", "dolu%", "hata"))
    for row in rows:
        print("  {:<8} {:>3}/{:<3} {:>7.1f} {:>10.1f} {:>8.1f}%   {}".format(
            row["mode"], row["ok"], row["total"], row["fps"], row["mean"],
            row["live"] * 100.0, row["error"][:46],
        ))


def verdict(open_rows, covered_rows):
    """Arka plan yakalama calisiyor mu? Insan okur karar."""
    by_mode = {r["mode"]: r for r in covered_rows}
    winners = [m for m in (wc.GRAB_CLIENT, wc.GRAB_WINDOW)
               if by_mode.get(m, {}).get("ok", 0) >= max(1, by_mode[m]["total"] // 2)
               and by_mode[m]["live"] > 0.05]
    print("\n=== KARAR ===")
    if winners:
        print("  GECTI: pencere ORTULUYKEN calisan varyant(lar): {}".format(
            ", ".join(winners)))
        print("  -> Arka plan modu yakalama tarafinda uygulanabilir.")
    else:
        print("  KALDI: ortulme altinda hicbir PrintWindow varyanti kare veremedi.")
        print("  -> Windows Graphics Capture (windows-capture) yedegine gecilmeli.")
    baseline = by_mode.get(wc.GRAB_BITBLT)
    if baseline is not None and open_rows:
        open_bitblt = {r["mode"]: r for r in open_rows}.get(wc.GRAB_BITBLT, {})
        print("  (kontrol) bitblt dolu%: acikken {:.1f}% -> ortuluyken {:.1f}%".format(
            open_bitblt.get("live", 0.0) * 100.0, baseline["live"] * 100.0))
    return bool(winners)


# --------------------------------------------------------------------- kesin kanit
def verify_occluded(app, hwnd, mode, out_dir):
    """ORTULU pencerede yakalananla EKRANDA GORUNENI karsilastirir.

    Ortme sirasinda ekranda ortucu (duz koyu) vardir. Bizim karemiz oyunu
    gosteriyor ve ekran karesinden FARKLIYSA, gercekten arka plandan
    okuyoruz demektir. Ayni cikiyorsa yalnizca ekrani kopyaliyoruz.
    """
    import mss

    rect = wc.window_bounds(hwnd)
    client = wc.window_client_bounds(hwnd)
    if not rect or not client:
        print("  Pencere olculeri alinamadi.")
        return False
    cx, cy, cw, ch = client

    cover = CoverWindow(rect)
    cover.place()
    cover.show()
    cover.raise_()
    for _ in range(30):
        app.processEvents()
        time.sleep(0.02)

    center = None
    try:
        # Ortme gercekten oldu mu? Merkez noktadaki pencere kimin?
        point = wintypes.POINT(cx + cw // 2, cy + ch // 2)
        user32 = ctypes.windll.user32
        user32.WindowFromPoint.argtypes = [wintypes.POINT]
        user32.WindowFromPoint.restype = wintypes.HWND
        user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
        user32.GetAncestor.restype = wintypes.HWND
        top = user32.WindowFromPoint(point)
        root = user32.GetAncestor(top, 2) if top else None       # GA_ROOT
        center = int(root) if root else (int(top) if top else None)
    except Exception as exc:
        print("  (ortme kontrolu yapilamadi: {})".format(exc))

    occluded = center is not None and center != hwnd
    print("  Merkezdeki ust pencere: 0x{:X} ({})".format(
        center or 0, "ORTUCU - ortme gercek" if occluded else "HEDEF - ortme YOK"))

    grabber = wc.WindowGrabber(lambda: hwnd, mode=mode)
    ours = None
    try:
        for _ in range(5):
            ours, _origin = grabber.grab()
            app.processEvents()
            time.sleep(0.1)
    finally:
        grabber.close()

    with mss.mss() as sct:
        shot = np.asarray(sct.grab({"left": cx, "top": cy,
                                    "width": cw, "height": ch}))
    screen = np.ascontiguousarray(shot[:, :, :3])

    cover.close()
    app.processEvents()

    if ours is None:
        print("  Yakalama BASARISIZ: {}".format(grabber.last_error))
        return False

    diff = float(np.abs(ours.astype(np.int16) - screen.astype(np.int16)).mean())
    print("  Bizim kare : ort={:.1f}  dolu%={:.1f}".format(
        float(ours.mean()), float((ours > 8).mean() * 100)))
    print("  Ekran karesi: ort={:.1f}  dolu%={:.1f}".format(
        float(screen.mean()), float((screen > 8).mean() * 100)))
    print("  Ortalama fark: {:.1f}".format(diff))

    try:
        import cv2

        os.makedirs(out_dir, exist_ok=True)
        cv2.imwrite(os.path.join(out_dir, "yakalanan_ortuluyken.png"), ours)
        cv2.imwrite(os.path.join(out_dir, "ekranda_gorunen.png"), screen)
        print("  PNG yazildi -> {}".format(out_dir))
    except Exception as exc:
        print("  PNG yazilamadi: {}".format(exc))

    proven = occluded and diff > 10.0
    print("\n=== KESIN KARAR ===")
    if proven:
        print("  GECTI: pencere ORTULUYKEN icerigi okunuyor (ekrandan FARKLI).")
        print("  -> Arka plan modu uygulanabilir. Varyant: {}".format(
            grabber.active_mode() or mode))
    elif not occluded:
        print("  BELIRSIZ: ortucu pencere hedefin onune gecemedi.")
    else:
        print("  KALDI: yakalanan kare ekrandakiyle ayni; ortulme okunamiyor.")
    return proven


# --------------------------------------------------------------------- girdi probu
def probe_key(hwnd, key):
    key = (key or "").upper()
    scan = KEYCODES.get(key)
    if scan is None:
        print("  '{}' KEYCODES icinde yok.".format(key))
        return False
    vk = wc.vk_from_scan(scan)
    down = wc.post_key_down(hwnd, vk, scan)
    time.sleep(0.05)
    up = wc.post_key_up(hwnd, vk, scan)
    print("  TUS '{}' scan=0x{:02X} vk=0x{:02X} -> down={} up={}".format(
        key, scan, vk, down, up))
    return down and up


def probe_click(hwnd, x, y, right=False):
    local = wc.screen_to_client(hwnd, x, y)
    if local is None:
        print("  ({}, {}) hedef pencerenin client alani DISINDA.".format(x, y))
        return False
    cx, cy = local
    target = wc.child_at_client_point(hwnd, cx, cy)
    button = wc.MK_RBUTTON if right else wc.MK_LBUTTON
    down = wc.WM_RBUTTONDOWN if right else wc.WM_LBUTTONDOWN
    up = wc.WM_RBUTTONUP if right else wc.WM_LBUTTONUP
    wc.post_mouse(target, wc.WM_MOUSEMOVE, 0, cx, cy)
    ok_down = wc.post_mouse(target, down, button, cx, cy)
    time.sleep(0.05)
    ok_up = wc.post_mouse(target, up, 0, cx, cy)
    print("  TIK ekran ({}, {}) -> client ({}, {}) hedef=0x{:X} down={} up={}".format(
        x, y, cx, cy, target, ok_down, ok_up))
    return ok_down and ok_up


# --------------------------------------------------------------------- ana akis
def main():
    parser = argparse.ArgumentParser(description="Pencere yakalama dogrulamasi")
    parser.add_argument("--title", default="", help="pencere basligindan bir parca")
    parser.add_argument("--list", action="store_true", help="pencereleri listele")
    parser.add_argument("--preview", action="store_true", help="canli onizleme ac")
    parser.add_argument("--cover", action="store_true",
                        help="hedefi opak pencereyle ort (ortulme testi)")
    parser.add_argument("--verify", action="store_true",
                        help="kesin kanit: ortuluyken yakalanan vs ekranda gorunen")
    parser.add_argument("--out", default="", help="--verify PNG cikti klasoru")
    parser.add_argument("--shot", default="", help="tek kare yakala ve PNG yaz")
    parser.add_argument("--frames", type=int, default=20, help="varyant basina kare")
    parser.add_argument("--mode", default=wc.GRAB_AUTO,
                        help="onizleme varyanti: auto/client/window/bitblt")
    parser.add_argument("--post-key", default="", help="PostMessage tus probu")
    parser.add_argument("--post-click", nargs=2, type=int, metavar=("X", "Y"),
                        help="PostMessage tik probu (ekran koordinati)")
    parser.add_argument("--post-right", action="store_true", help="tik probu sag tus")
    args = parser.parse_args()

    if not wc.WINAPI_AVAILABLE:
        print("Windows API kullanilamiyor.")
        return 2

    if args.list or not args.title:
        windows = wc.list_windows(args.title)
        print("Gorunur pencereler ({}):".format(len(windows)))
        for item in sorted(windows, key=lambda w: -w["client"][2] * w["client"][3]):
            print("  0x{:<12X} {:>5}  {:>18}  {}".format(
                item["hwnd"], item["pid"], str(item["client"][2:]), item["title"][:60]))
        if not args.title:
            print("\nOlcum icin: --title \"<baslik parcasi>\"")
        return 0

    hwnd = wc.find_game_window(args.title)
    if not hwnd:
        print("'{}' basligiyla eslesen pencere BULUNAMADI.".format(args.title))
        print("Acik mi? --list ile bakabilirsin.")
        return 1

    print("Hedef pencere:")
    print(describe(hwnd))

    app = QApplication(sys.argv)

    if args.post_key:
        print("\n--- PostMessage tus probu ---")
        probe_key(hwnd, args.post_key)
    if args.post_click:
        print("\n--- PostMessage tik probu ---")
        probe_click(hwnd, args.post_click[0], args.post_click[1], args.post_right)
    if args.shot:
        grabber = wc.WindowGrabber(lambda: hwnd, mode=args.mode)
        frame = None
        try:
            for _ in range(3):
                frame, _origin = grabber.grab()
                time.sleep(0.15)
        finally:
            grabber.close()
        if frame is None:
            print("\nYakalanamadi: {}".format(grabber.last_error))
            return 1
        import cv2

        cv2.imwrite(args.shot, frame)
        print("\nKare yazildi: {}  ({}x{}, varyant={})".format(
            args.shot, frame.shape[1], frame.shape[0], grabber.active_mode()))
        return 0

    if args.post_key or args.post_click:
        if not args.preview:
            return 0

    if args.verify:
        print("\n--- KESIN KANIT TESTI ({}) ---".format(args.mode))
        out_dir = args.out or os.path.join(os.path.dirname(__file__), "_yakalama")
        ok = verify_occluded(app, hwnd, args.mode, out_dir)
        return 0 if ok else 1

    if args.preview:
        cover = None
        if args.cover:
            rect = wc.window_bounds(hwnd)
            if rect:
                cover = CoverWindow(rect)
                cover.place()
                cover.show()
        preview = PreviewWindow(hwnd, args.mode)
        preview.show()
        preview.raise_()
        result = app.exec_()
        if cover is not None:
            cover.close()
        return result

    def pump():
        app.processEvents()

    open_rows = [measure(hwnd, mode, args.frames, pump) for mode in VARIANTS]
    print_report("PENCERE ACIKTA (kontrol)", open_rows)

    covered_rows = []
    if args.cover:
        rect = wc.window_bounds(hwnd)
        if not rect:
            print("Pencere dikdortgeni alinamadi; ortme testi atlandi.")
        else:
            cover = CoverWindow(rect)
            cover.place()
            cover.show()
            cover.raise_()
            for _ in range(20):
                app.processEvents()
                time.sleep(0.02)
            try:
                covered_rows = [measure(hwnd, mode, args.frames, pump)
                                for mode in VARIANTS]
            finally:
                cover.close()
                app.processEvents()
            print_report("PENCERE TAMAMEN ORTULU", covered_rows)
            verdict(open_rows, covered_rows)
    else:
        print("\n(Ortulme testi icin --cover ekle.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
