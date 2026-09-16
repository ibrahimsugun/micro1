"""Planin "Dogrulama" bolumu: GERCEK tus/tik gonderimi -> dummy'nin log listesi.

Diger testler sahte bir InputService kullanir. Bu test gercek InputService ile
(Interception varsa sürücü, yoksa PyAutoGUI/win32 yedegi) tus ve tik gonderir
ve dummy pencerenin kayit listesinden dogrular. Yani girdi yolu ucdan uca
denenmis olur.

UYARI: gercek tus/tik gonderir. Dummy pencere en ustte ve odakta tutulur;
testin fare imleci konumu sonunda geri alinir.
"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from PyQt5.QtCore import QPoint, QRect, Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app.app_state import AppState  # noqa: E402
from app.calibration.calibration_manager import CalibrationManager  # noqa: E402
from app.calibration.calibration_model import CalibrationRegion  # noqa: E402
from app.constants import CALIB_HP, CALIB_PARTY, NO_PAGE  # noqa: E402
from app.core import vision  # noqa: E402
from app.core.module_base import ModuleContext  # noqa: E402
from app.core.party_tracker import PartyTracker  # noqa: E402
from app.live_status import LiveStatus  # noqa: E402
from app.modules.heal_module import HealModule  # noqa: E402
from app.modules.pot_module import PotModule  # noqa: E402
from app.services.input_service import InputService  # noqa: E402
from app.services.screen_scanner import ScreenScanner  # noqa: E402
from app.services.sound_service import SoundService  # noqa: E402

from dummy_game_window import (  # noqa: E402
    HP_RECT, PARTY_ORIGIN, PARTY_ROW_H, PARTY_ROW_W, DummyGameWindow,
)

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("[{}] {}{}".format("PASS" if ok else "FAIL", name,
                             ("  -- " + detail) if detail else ""))


def pump(app, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def global_rect(widget, rect):
    tl = widget.mapToGlobal(QPoint(rect.x(), rect.y()))
    ratio = widget.devicePixelRatioF()
    return (int(tl.x() * ratio), int(tl.y() * ratio),
            int(rect.width() * ratio), int(rect.height() * ratio))


def sample(scanner, name, rect):
    img = scanner.region(rect)
    ref = vision.saturated_dominant_color(img)
    region = CalibrationRegion(name, rect=rect, ref_color=ref,
                               ratio_full=max(0.01, vision.match_ratio(img, ref)))
    region.saved = True
    return region


def log_lines(dummy):
    return [dummy.log.item(i).text() for i in range(dummy.log.count())]


def focus(dummy, app, tries=6):
    """Dummy'yi gercekten on plana al ve dogrula.

    Gercek tus gonderimi ODAKTAKI pencereye gider; odak alinamazsa test
    yaniltici sekilde patlar. Windows SetForegroundWindow'u bazen reddettigi
    icin birkac kez denenir ve sonuc dogrulanir.
    """
    import win32api
    import win32con
    import win32gui
    import win32process

    hwnd = int(dummy.winId())
    for _ in range(tries):
        dummy.raise_()
        dummy.activateWindow()
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            # Windows, on planda olmayan bir surecin SetForegroundWindow
            # cagrisini reddeder. Standart cozum: on plandaki pencerenin girdi
            # kuyruguna gecici olarak baglanip cagriyi oradan yapmak.
            foreground = win32gui.GetForegroundWindow()
            target_thread = win32process.GetWindowThreadProcessId(foreground)[0]
            own_thread = win32api.GetCurrentThreadId()
            attached = False
            if target_thread and target_thread != own_thread:
                attached = bool(
                    win32process.AttachThreadInput(target_thread, own_thread, True)
                )
            try:
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
            finally:
                if attached:
                    win32process.AttachThreadInput(target_thread, own_thread, False)
        except Exception:
            pass
        pump(app, 0.35)
        if win32gui.GetForegroundWindow() == hwnd:
            return True
    return False


def main():
    app = QApplication(sys.argv)
    dummy = DummyGameWindow()
    dummy.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    dummy.move(60, 60)
    dummy.show()
    focus(dummy, app)
    pump(app, 1.0)

    state = AppState()
    live = LiveStatus()
    scanner = ScreenScanner(live_status=live, fps=20)
    scanner.start()
    pump(app, 1.0)

    calib = CalibrationManager()
    real_input = InputService(state)
    ctx = ModuleContext(state, real_input, scanner, calib, live, SoundService(False))
    party = PartyTracker(scanner, calib)
    canvas = dummy.canvas

    print("girdi arka ucu:", real_input.backend)
    calib.save_region(sample(scanner, CALIB_HP, global_rect(canvas, HP_RECT)))
    calib.save_region(sample(scanner, CALIB_PARTY, global_rect(
        canvas, QRect(PARTY_ORIGIN[0], PARTY_ORIGIN[1], PARTY_ROW_W, PARTY_ROW_H * 2))))

    state.master_on.set()
    state.game_focused.set()

    # ------------------------------------------------- gercek tus + F sayfasi
    pot = PotModule(ctx)
    pot.set_config({
        "hp": {"enabled": True, "threshold": 50, "key": "1", "fpage": "F2"},
        "mp": {"enabled": False},
        "minor": {"enabled": False},
        "third": {"enabled": False},
    })
    dummy.log.clear()
    dummy.hp_slider.setValue(30)
    if not focus(dummy, app):
        print("UYARI: dummy pencere on plana alinamadi; test atlaniyor.")
        scanner.stop()
        dummy.close()
        return 2
    pot.set_enabled(True)
    pot.start()
    pump(app, 2.0)
    pot.set_enabled(False)
    pot.stop()
    pump(app, 0.4)

    lines = log_lines(dummy)
    keys = [l.split("TUŞ: ")[1].split(" ")[0] for l in lines if "TUŞ:" in l]
    check("Dummy gercek tus aldi", bool(keys), str(lines[:4]))
    check("Gonderilen tus dogru ('1')", "1" in keys, str(keys))
    check("F sayfasi ONCE, tus SONRA gonderildi",
          keys[:2] == ["F2", "1"] if len(keys) >= 2 else False, str(keys[:4]))
    if len(keys) >= 2:
        stamps = [l for l in lines if "TUŞ:" in l]
        gap = stamps[1].split("(+")[-1].rstrip(" ms)") if "(+" in stamps[1] else "?"
        check("F sayfasi ile tus arasi ~100 ms",
              gap.isdigit() and 80 <= int(gap) <= 260, "{} ms".format(gap))

    dummy.hp_slider.setValue(100)
    pump(app, 0.4)

    # ------------------------------------------------- gercek tik (parti heal)
    try:
        import win32api

        cursor_before = win32api.GetCursorPos()
    except Exception:
        cursor_before = None

    heal = HealModule(ctx, party)
    heal.set_config({
        "single": {"enabled": True, "threshold": 70, "key": "6",
                   "fpage": NO_PAGE, "party_click": True},
        "party": {"enabled": False},
    })
    dummy.count_spin.setValue(4)
    for i in range(4):
        dummy.member_sliders[i].setValue(100)
    dummy.member_sliders[2].setValue(35)
    party.request_rescan()
    focus(dummy, app)
    pump(app, 0.6)
    check("Dummy pencere on planda (gercek girdi icin sart)",
          focus(dummy, app))
    dummy.log.clear()

    heal.set_enabled(True)
    heal.start()
    pump(app, 1.6)
    heal.set_enabled(False)
    heal.stop()
    pump(app, 0.5)

    lines = log_lines(dummy)
    clicks = [l for l in lines if "TIK:" in l]
    keys = [l for l in lines if "TUŞ:" in l]
    check("Dummy gercek tik aldi", bool(clicks), str(lines[:4]))
    check("Tik 3. parti uyesinin satirina dustu",
          any("Parti üyesi 3" in l for l in clicks), str(clicks[:2]))
    check("Tiktan sonra heal tusu geldi",
          any("TUŞ: 6" in l for l in keys), str(keys[:3]))

    if cursor_before is not None:
        try:
            import win32api

            win32api.SetCursorPos(cursor_before)
        except Exception:
            pass

    scanner.stop()
    dummy.close()

    print("\n" + "=" * 60)
    failed = [n for n, ok in RESULTS if not ok]
    print("Toplam {} kontrol, {} basarisiz".format(len(RESULTS), len(failed)))
    for name in failed:
        print("  BASARISIZ: " + name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
