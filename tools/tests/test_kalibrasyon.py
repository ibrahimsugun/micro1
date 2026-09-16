"""Kalibrasyon cercevesi, yakalama kalkani ve INI kaliciligi testleri."""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtCore import QPoint, QRect, Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app.calibration.frame_window import FrameWindow  # noqa: E402
from app.constants import (  # noqa: E402
    CALIB_HP, CALIB_PARTY, CALIB_RPR, CALIB_TARGET,
)
from app.core import vision  # noqa: E402
from app.live_status import LiveStatus  # noqa: E402
from app.services.capture_shield import exclude_from_capture  # noqa: E402
from app.services.screen_scanner import ScreenScanner  # noqa: E402

from ortak import force_foreground  # noqa: E402

from dummy_game_window import (  # noqa: E402
    HP_RECT, PARTY_ORIGIN, PARTY_ROW_H, PARTY_ROW_W, RPR_RECT, DummyGameWindow,
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
    r = widget.devicePixelRatioF()
    return (int(tl.x() * r), int(tl.y() * r),
            int(rect.width() * r), int(rect.height() * r))


app = QApplication(sys.argv)

dummy = DummyGameWindow()
dummy.setWindowFlag(Qt.WindowStaysOnTopHint, True)
dummy.move(60, 60)
dummy.show()
force_foreground(dummy, app)
pump(app, 1.5)

scanner = ScreenScanner(live_status=LiveStatus(), fps=20)
scanner.start()
pump(app, 1.0)

canvas = dummy.canvas
hp_rect = global_rect(canvas, HP_RECT)

# --------------------------------------------------------------- kalkan testi
baseline = scanner.region(hp_rect).copy()
frame = FrameWindow(CALIB_HP)
frame.apply_body_rect(hp_rect)
frame.show()
frame.raise_()
pump(app, 1.2)

shielded = exclude_from_capture(frame)
pump(app, 0.6)
covered = scanner.region(hp_rect)
same = bool((baseline == covered).all())
check("Cerceve ekran yakalamadan cikarildi", shielded)
check("Cerceve alttaki bari bozmuyor", same,
      "shield={}".format(shielded))

# capture_rect gerceklen barin uzerinde mi?
produced = frame.capture_rect()
close = all(abs(a - b) <= 3 for a, b in zip(produced, hp_rect))
check("capture_rect / apply_body_rect gidis-donusu tutuyor", close,
      "verilen={} alinan={}".format(hp_rect, produced))

dummy.hp_slider.setValue(70)
pump(app, 0.6)
img = scanner.region(produced)
ref = vision.saturated_dominant_color(img[:, :max(2, int(img.shape[1] * 0.15))])
percent = vision.fill_fraction_by_column(img, ref)
check("Cerceve icinden canli okuma dogru", abs(percent - 70) <= 6,
      "okunan=%.1f" % percent)
dummy.hp_slider.setValue(100)
frame.close()
pump(app, 0.3)

# --------------------------------------------------------------- INI kaliciligi
from app.calibration.calibration_manager import CalibrationManager  # noqa: E402
from app.calibration.calibration_model import CalibrationRegion  # noqa: E402
from app.config.settings_manager import SettingsManager  # noqa: E402

calib = CalibrationManager()
pump(app, 0.4)

hp_region = CalibrationRegion(CALIB_HP, rect=hp_rect)
img = scanner.region(hp_rect)
hp_region.ref_color = vision.saturated_dominant_color(img)
hp_region.ratio_full = vision.match_ratio(img, hp_region.ref_color)
calib.save_region(hp_region)

# RPR artik RENK ile kaydediliyor (sablon degil): iki silah da yanikken.
dummy.left_burnt_check.setChecked(True)
dummy.right_burnt_check.setChecked(True)
pump(app, 0.5)
rpr_rect = global_rect(canvas, RPR_RECT)
rpr_img = scanner.region(rpr_rect)
rpr_region = CalibrationRegion(CALIB_RPR, rect=rpr_rect)
rpr_region.ref_color = vision.vivid_dominant_color(rpr_img)
rpr_region.ratio_full = vision.color_presence_ratio(rpr_img, rpr_region.ref_color)
calib.save_region(rpr_region)
check("RPR yanik rengi orneklendi", rpr_region.ratio_full > 0.02,
      "oran %{:.1f}".format(rpr_region.ratio_full * 100))

party_rect = global_rect(
    canvas, QRect(PARTY_ORIGIN[0], PARTY_ORIGIN[1], PARTY_ROW_W, PARTY_ROW_H * 2)
)
party_region = CalibrationRegion(CALIB_PARTY, rect=party_rect)
img = scanner.region(party_rect)
party_region.ref_color = vision.saturated_dominant_color(img)
party_region.ratio_full = vision.match_ratio(img, party_region.ref_color)
calib.save_region(party_region)
calib.screen_size = scanner.screen_size()

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_calib_test.ini")
if os.path.exists(path):
    os.remove(path)
settings = SettingsManager(path)
settings.load()
settings.current_profile = "test profili"
settings.create_profile("test profili")
settings.set_section("Calibration", calib.to_dict())
settings.save()

settings2 = SettingsManager(path)
settings2.load()
check("Son profil hatirlandi", settings2.current_profile == "test profili",
      settings2.current_profile)
calib2 = CalibrationManager()
calib2.load_dict(settings2.get_section("Calibration"))
check("HP kaydi INI'den geri geldi",
      calib2.rect(CALIB_HP) == tuple(hp_rect)
      and calib2.get(CALIB_HP).ref_color == hp_region.ref_color,
      "{}".format(calib2.get(CALIB_HP).summary()))
check("ratio_full korundu",
      abs(calib2.get(CALIB_HP).ratio_full - hp_region.ratio_full) < 1e-6)
rpr2 = calib2.get(CALIB_RPR)
check("RPR renk kaydi INI turundan sonra korundu",
      rpr2.ref_color == rpr_region.ref_color
      and abs(rpr2.ratio_full - rpr_region.ratio_full) < 1e-6,
      str(rpr2.ref_color))
# Kayitlar FIZIKSEL pikseldir: %125 olcekte satir yuksekligi de olceklenir.
ratio = canvas.devicePixelRatioF()
beklenen_satir = round(PARTY_ROW_H * ratio)
check("Parti satir yuksekligi kalici (olcek farkindaligiyla)",
      abs(calib2.party_row_height() - beklenen_satir) <= 1,
      "olcek={} bulunan={} beklenen={}".format(
          ratio, calib2.party_row_height(), beklenen_satir))
check("Ekran boyutu kaydedildi",
      calib2.screen_size == tuple(scanner.screen_size()),
      str(calib2.screen_size))
check("Kayitsiz bolge listesi dogru",
      set(calib2.unsaved_names()) == {"mp_bar", CALIB_TARGET},
      str(calib2.unsaved_names()))
check("Eksik kalibrasyon tespiti",
      calib2.missing([CALIB_HP, CALIB_TARGET]) == [CALIB_TARGET])

# --- bar geometrisi: kalicilik ve eski profil uyumu -----------------------
# HP ailesi renkten bagimsiz okunmak icin barin bolge icindeki YERINI bilmek
# zorunda. Bu bilgi profile yazilip geri okunabilmeli; ESKI profillerde ise
# alan hic yoktur ve yuklemeyi bozmamalidir.
from app.core.vision import BarGeometry  # noqa: E402

ornek = BarGeometry(0.02, 0.98, 0.15, 0.30)
bolge = CalibrationRegion(CALIB_HP, rect=(10, 20, 200, 24))
bolge.ref_color = (30, 30, 200)
bolge.bar_geom = ornek
geri = CalibrationRegion.from_dict(CALIB_HP, bolge.to_dict())
check("Bar geometrisi profile yazilip geri okunuyor", geri.bar_geom == ornek,
      str(geri.bar_geom))

eski = CalibrationRegion.from_dict(
    CALIB_HP, {"rect": [10, 20, 200, 24], "ref_color": [30, 30, 200],
               "ratio_full": 0.62})
check("Eski profil (geometrisiz) sorunsuz yukleniyor",
      eski.saved and eski.bar_geom is None and abs(eski.ratio_full - 0.62) < 1e-6)

bozuk = CalibrationRegion.from_dict(
    CALIB_HP, {"rect": [10, 20, 200, 24], "bar_geom": [0.9, 0.1, 0.0, 1.0]})
check("Bozuk geometri reddediliyor (eski yola dusulur)", bozuk.bar_geom is None)

with open(path, encoding="utf-8") as handle:
    raw = handle.read()
check("INI bolum semasi plana uygun",
      "[Profile_test profili.Calibration]" in raw, raw.splitlines()[0])

os.remove(path)
scanner.stop()
dummy.close()

print("\n" + "=" * 60)
failed = [n for n, ok in RESULTS if not ok]
print("Toplam {} kontrol, {} basarisiz".format(len(RESULTS), len(failed)))
for name in failed:
    print("  BASARISIZ: " + name)
sys.exit(1 if failed else 0)
