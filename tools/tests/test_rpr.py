"""RPR (yanık silah) tespiti: el, yön ve zemin bağımsızlığı.

Kullanıcı geri bildirimi: silah sağ elde, sol elde veya iki elde birden
yanabilir; kılıcın yönü değişebilir; arka plan HERHANGİ bir renk olabilir.
Tespit bu yüzden şablon eşleştirme değil, kaydedilen yanık RENGİNİN dar bir
HSV bandına düşen piksel oranıdır.

Kalibrasyon senaryosu kullanıcının yaptığıyla aynı: İKİ silah da yanıkken
kaydedilir; sonraki tüm durumlar bu kayda göre değerlendirilir.
"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtCore import QPoint, Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app.app_state import AppState  # noqa: E402
from app.calibration.calibration_manager import CalibrationManager  # noqa: E402
from app.calibration.calibration_model import CalibrationRegion  # noqa: E402
from app.constants import CALIB_RPR, RPR_TRIGGER_FRACTION  # noqa: E402
from app.core import vision  # noqa: E402
from app.core.module_base import ModuleContext  # noqa: E402
from app.live_status import LiveStatus  # noqa: E402
from app.services.screen_scanner import ScreenScanner  # noqa: E402
from app.services.sound_service import SoundService  # noqa: E402

from ortak import force_foreground  # noqa: E402

from dummy_game_window import (  # noqa: E402
    RPR_RECT, TERRAIN_PRESETS, DummyGameWindow,
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


def set_state(app, dummy, left, right, angle=None, terrain=None):
    if terrain is not None:
        dummy.terrain_combo.setCurrentIndex(terrain)
    if angle is not None:
        dummy.angle_slider.setValue(angle)
    dummy.left_burnt_check.setChecked(left)
    dummy.right_burnt_check.setChecked(right)
    pump(app, 0.35)


def main():
    app = QApplication(sys.argv)
    dummy = DummyGameWindow()
    dummy.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    dummy.move(60, 60)
    dummy.show()
    force_foreground(dummy, app)
    pump(app, 1.4)

    state = AppState()
    scanner = ScreenScanner(live_status=LiveStatus(), fps=20)
    scanner.start()
    pump(app, 1.0)

    calib = CalibrationManager()
    ctx = ModuleContext(state, None, scanner, calib, LiveStatus(),
                        SoundService(False))
    rect = global_rect(dummy.canvas, RPR_RECT)

    # ------------------------------------------------- kalibrasyon (iki el yanık)
    set_state(app, dummy, True, True, angle=25, terrain=0)
    image = scanner.region(rect)
    ref = vision.vivid_dominant_color(image)
    region = CalibrationRegion(CALIB_RPR, rect=rect, ref_color=ref)
    region.ratio_full = max(0.002, vision.color_presence_ratio(image, ref))
    region.saved = True
    calib.save_region(region)
    print("referans renk (BGR):", ref,
          "| kayıt oranı: %{:.1f}".format(region.ratio_full * 100),
          "| eşik: %{:.1f}".format(region.ratio_full * RPR_TRIGGER_FRACTION * 100))
    check("Kayıt anında yanık rengi bulundu", region.ratio_full > 0.02,
          "%{:.1f}".format(region.ratio_full * 100))
    check("Kayıt hemen ardından KIRIK okunuyor", ctx.rpr_broken())

    # ------------------------------------------------- hangi el yanık olursa olsun
    for left, right, beklenen, ad in (
        (True, True, True, "iki el de yanık"),
        (True, False, True, "yalnız SOL el yanık"),
        (False, True, True, "yalnız SAĞ el yanık"),
        (False, False, False, "ikisi de sağlam"),
    ):
        set_state(app, dummy, left, right)
        ratio = ctx.rpr_ratio()
        check("El durumu: {} -> {}".format(ad, "KIRIK" if beklenen else "sağlam"),
              ctx.rpr_broken() is beklenen,
              "oran %{:.1f}".format(ratio * 100))

    # ------------------------------------------------- kılıcın yönü fark etmemeli
    for angle in (0, 45, 90, 135, 180):
        set_state(app, dummy, True, True, angle=angle)
        check("Yön {}° iken iki el yanık -> KIRIK".format(angle), ctx.rpr_broken(),
              "oran %{:.1f}".format(ctx.rpr_ratio() * 100))
        set_state(app, dummy, False, True, angle=angle)
        check("Yön {}° iken tek el yanık -> KIRIK".format(angle), ctx.rpr_broken(),
              "oran %{:.1f}".format(ctx.rpr_ratio() * 100))
        set_state(app, dummy, False, False, angle=angle)
        check("Yön {}° iken sağlam -> sağlam".format(angle), not ctx.rpr_broken(),
              "oran %{:.1f}".format(ctx.rpr_ratio() * 100))

    # ------------------------------------------------- zemin herhangi bir renk
    for index, (caption, _color) in enumerate(TERRAIN_PRESETS):
        set_state(app, dummy, False, False, angle=25, terrain=index)
        check("Zemin '{}': silahlar sağlamken yanlış alarm yok".format(caption),
              not ctx.rpr_broken(), "oran %{:.1f}".format(ctx.rpr_ratio() * 100))
        set_state(app, dummy, False, True, angle=25, terrain=index)
        check("Zemin '{}': tek el yanık yakalandı".format(caption),
              ctx.rpr_broken(), "oran %{:.1f}".format(ctx.rpr_ratio() * 100))

    scanner.stop()
    dummy.close()

    print("\n" + "=" * 60)
    failed = [n for n, ok in RESULTS if not ok]
    print("Toplam {} kontrol, {} başarısız".format(len(RESULTS), len(failed)))
    for name in failed:
        print("  BASARISIZ: " + name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
