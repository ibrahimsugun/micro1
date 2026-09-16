"""Can barının RENGİ değişince okunan yüzde değişmemeli (canlı ekran).

Gerçek oyunda yaratıkların atağına göre HP barının rengi değişiyor: yanarken
turuncu, light/zehir/malice grubunda mor, ice'ta sarı-yeşil. Eski ölçüm kayıt
anındaki TONA maske uyguladığı için renk değişince %0 okuyor ve ölüm koruması
beş saniye sonra tüm modülleri durduruyordu.

Yeni ölçüm barın BOŞ kısmını sayar; boş kısım rengi ne olursa olsun siyah
kaldığı için sonuç renkten bağımsızdır. Bu test tam olarak bunu doğrular:
aynı can seviyesinde renk değiştirilir, okunan yüzde SABİT kalmalı.

Renk etiketi ayrıca kontrol edilir ama hiçbir modül kararına bağlı değildir.
"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtCore import QPoint, QRect, Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app.calibration.calibration_manager import CalibrationManager  # noqa: E402
from app.calibration.calibration_model import CalibrationRegion  # noqa: E402
from app.constants import CALIB_HP, CALIB_PARTY  # noqa: E402
from app.core import vision  # noqa: E402
from app.core.module_base import ModuleContext  # noqa: E402
from app.core.party_tracker import PartyTracker  # noqa: E402
from app.live_status import LiveStatus  # noqa: E402
from app.services.screen_scanner import ScreenScanner  # noqa: E402

from ortak import force_foreground  # noqa: E402

from dummy_game_window import (  # noqa: E402
    HP_RECT, PARTY_ORIGIN, PARTY_ROW_H, PARTY_ROW_W, DummyGameWindow,
)

HP_LEVEL = 65
TOLERANCE = 6.0          # puan — degrade ve yazı payı
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


def main():
    app = QApplication(sys.argv)
    dummy = DummyGameWindow()
    dummy.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    dummy.move(60, 60)
    dummy.show()
    force_foreground(dummy, app)
    pump(app, 1.4)

    canvas = dummy.canvas
    scanner = ScreenScanner(live_status=LiveStatus(), fps=20)
    scanner.start()
    pump(app, 1.0)

    calib = CalibrationManager()
    ctx = ModuleContext(None, None, scanner, calib, None, None)

    # ------------------------------------------------ kayıt: can NORMAL renkte
    dummy.hp_slider.setValue(HP_LEVEL)
    dummy.hp_color_combo.setCurrentIndex(0)
    dummy.party_color_combo.setCurrentIndex(0)
    dummy.count_spin.setValue(4)
    pump(app, 0.5)

    hp_rect = global_rect(canvas, HP_RECT)
    image = scanner.region(hp_rect)
    region = CalibrationRegion(CALIB_HP, rect=hp_rect)
    region.ref_color = vision.saturated_dominant_color(image)
    region.ratio_full = max(0.01, vision.match_ratio(image, region.ref_color))
    region.bar_geom = vision.detect_bar_geometry(image, region.ref_color)
    check("HP barının yeri kayıt anında çıkarıldı", region.bar_geom is not None,
          str(region.bar_geom))
    calib.save_region(region)

    party_rect = global_rect(
        canvas, QRect(PARTY_ORIGIN[0], PARTY_ORIGIN[1], PARTY_ROW_W, PARTY_ROW_H * 2)
    )
    party_image = scanner.region(party_rect)
    party_region = CalibrationRegion(CALIB_PARTY, rect=party_rect)
    party_region.ref_color = vision.saturated_dominant_color(party_image)
    row = party_image[:party_image.shape[0] // 2]
    party_region.bar_geom = (vision.detect_bar_geometry(row, party_region.ref_color)
                             or vision.detect_bar_geometry(row, None))
    check("Parti satırının yeri kayıt anında çıkarıldı",
          party_region.bar_geom is not None, str(party_region.bar_geom))
    calib.save_region(party_region)

    tracker = PartyTracker(scanner, calib)
    tracker.set_manual_count(4)

    taban = ctx.bar_percent(CALIB_HP)
    check("Normal renkte can doğru okunuyor",
          taban is not None and abs(taban - HP_LEVEL) <= TOLERANCE,
          "okunan %{:.1f}, beklenen %{}".format(taban or -1, HP_LEVEL))

    # -------------------------------------------- renk değişince yüzde SABİT
    beklenen_durum = ["normal", "yanma", "yavaslatma", "mor"]
    for index in range(dummy.hp_color_combo.count()):
        etiket = dummy.hp_color_combo.itemText(index)
        dummy.hp_color_combo.setCurrentIndex(index)
        pump(app, 0.45)

        okunan = ctx.bar_percent(CALIB_HP)
        check("'{}' renginde can yine %{}".format(etiket, HP_LEVEL),
              okunan is not None and abs(okunan - HP_LEVEL) <= TOLERANCE,
              "okunan %{:.1f}".format(okunan if okunan is not None else -1))

        durum = ctx.bar_state(CALIB_HP)
        check("'{}' rengi '{}' olarak etiketlendi".format(etiket, beklenen_durum[index]),
              durum == beklenen_durum[index], "okunan '{}'".format(durum))

    # ------------------------------------------------ parti: renk bağımsızlığı
    dummy.hp_color_combo.setCurrentIndex(0)
    for index in range(dummy.party_color_combo.count()):
        etiket = dummy.party_color_combo.itemText(index)
        dummy.party_color_combo.setCurrentIndex(index)
        pump(app, 0.45)
        tracker.request_rescan()
        members = tracker.update(force=True)
        check("Parti '{}' renginde 4 üye okunuyor".format(etiket), len(members) == 4,
              str([round(m["percent"]) for m in members]))
        if members:
            dolu = [m["percent"] for m in members if m["present"]]
            check("Parti '{}' renginde canlar sıfırlanmadı".format(etiket),
                  all(p > 5.0 for p in dolu),
                  str([round(p) for p in dolu]))

    # ------------------------------- can seviyesi değişince ölçüm takip ediyor
    dummy.hp_color_combo.setCurrentIndex(3)           # mor debuff
    for seviye in (100, 40, 15):
        dummy.hp_slider.setValue(seviye)
        pump(app, 0.45)
        okunan = ctx.bar_percent(CALIB_HP)
        check("Mor barda can %{} okunuyor".format(seviye),
              okunan is not None and abs(okunan - seviye) <= TOLERANCE,
              "okunan %{:.1f}".format(okunan if okunan is not None else -1))

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
