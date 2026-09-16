"""Dummy pencereye karsi uctan uca dogrulama.

Gercek ekran yakalama + gercek vision kodu + gercek modul thread'leri.
Tus/tik gonderimi sahte bir InputService ile kaydedilir (oyuna gitmez).
"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from PyQt5.QtCore import QPoint, Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app.app_state import AppState  # noqa: E402
from app.calibration.calibration_manager import CalibrationManager  # noqa: E402
from app.calibration.calibration_model import CalibrationRegion  # noqa: E402
from app.constants import (  # noqa: E402
    NO_PAGE,
    CALIB_HP, CALIB_MP, CALIB_PARTY, CALIB_RPR, CALIB_TARGET,
)
from app.core import vision  # noqa: E402
from app.core.module_base import ModuleContext  # noqa: E402
from app.core.party_tracker import PartyTracker  # noqa: E402
from app.live_status import LiveStatus  # noqa: E402
from app.modules.attack_module import AttackModule  # noqa: E402
from app.modules.buff_module import BuffModule  # noqa: E402
from app.modules.clicker_module import ClickerModule, click_action, key_action  # noqa: E402
from app.modules.heal_module import HealModule  # noqa: E402
from app.modules.pot_module import PotModule  # noqa: E402
from app.services.screen_scanner import ScreenScanner  # noqa: E402
from app.services.sound_service import SoundService  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ortak import force_foreground  # noqa: E402
from dummy_game_window import DummyGameWindow  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    mark = "PASS" if condition else "FAIL"
    print("[{}] {}{}".format(mark, name, ("  -- " + detail) if detail else ""))


class FakeInput:
    """InputService yerine gecer; cagrilari zaman damgasiyla kaydeder."""

    backend = "TEST"

    def __init__(self):
        self.events = []

    def _log(self, kind, payload):
        self.events.append((time.monotonic(), kind, payload))

    def press_key(self, key, hold_s=None):
        self._log("key", key.upper())
        return True

    def press_with_page(self, page, key):
        self._log("page_key", (page, key.upper()))
        return True

    def press_raw(self, key):
        self._log("raw", key)
        return True

    def click(self, x, y, right=False):
        self._log("click", (int(x), int(y), right))
        return True

    def move_to(self, x, y):
        return True

    def keys(self):
        return [p for _t, k, p in self.events if k == "key"]

    def page_keys(self):
        return [p for _t, k, p in self.events if k == "page_key"]

    def clicks(self):
        return [p for _t, k, p in self.events if k == "click"]

    def stamps(self, kind, match=None):
        return [t for t, k, p in self.events
                if k == kind and (match is None or p == match)]

    def clear(self):
        self.events = []


def pump(app, seconds):
    """Qt olay dongusunu isletirken bekle (dummy pencere cizilmeye devam etsin)."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def global_rect(widget, rect):
    top_left = widget.mapToGlobal(QPoint(rect.x(), rect.y()))
    ratio = widget.devicePixelRatioF()
    return (int(top_left.x() * ratio), int(top_left.y() * ratio),
            int(rect.width() * ratio), int(rect.height() * ratio))


def sample_region(scanner, name, rect, template=False):
    image = scanner.region(rect)
    assert image is not None and image.size, "bolge okunamadi: " + name
    region = CalibrationRegion(name, rect=rect)
    if template:
        region.set_template_from_image(image)
    else:
        ref = vision.saturated_dominant_color(image)
        region.ref_color = ref
        region.ratio_full = max(0.01, vision.match_ratio(image, ref))
    region.saved = True
    return region


def main():
    app = QApplication(sys.argv)
    dummy = DummyGameWindow()
    # Test boyunca terminal penceresi dummy'yi kapatmasin: ustte tut.
    dummy.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    dummy.move(60, 60)
    dummy.show()
    force_foreground(dummy, app)
    pump(app, 1.5)

    state = AppState()
    live = LiveStatus()
    scanner = ScreenScanner(live_status=live, fps=20)
    scanner.start()
    pump(app, 1.0)

    calib = CalibrationManager()
    fake_input = FakeInput()
    ctx = ModuleContext(state, fake_input, scanner, calib, live, SoundService(False))
    party = PartyTracker(scanner, calib)

    canvas = dummy.canvas
    from dummy_game_window import (
        HP_RECT, MP_RECT, PARTY_ORIGIN, PARTY_ROW_H, PARTY_ROW_W, RPR_RECT,
        TARGET_RECT,
    )
    from PyQt5.QtCore import QRect

    # ---------------------------------------------------------------- kayit
    calib.save_region(sample_region(scanner, CALIB_HP, global_rect(canvas, HP_RECT)))
    calib.save_region(sample_region(scanner, CALIB_MP, global_rect(canvas, MP_RECT)))
    calib.save_region(
        sample_region(scanner, CALIB_TARGET, global_rect(canvas, TARGET_RECT))
    )
    party_rect = QRect(PARTY_ORIGIN[0], PARTY_ORIGIN[1], PARTY_ROW_W, PARTY_ROW_H * 2)
    calib.save_region(
        sample_region(scanner, CALIB_PARTY, global_rect(canvas, party_rect))
    )
    check("HP/MP/hedef/parti kayitlari olustu",
          all(calib.is_saved(n) for n in (CALIB_HP, CALIB_MP, CALIB_TARGET,
                                          CALIB_PARTY)))
    # Kayitlar FIZIKSEL pikseldir: %125 olcekte satir yuksekligi de olceklenir.
    ratio = canvas.devicePixelRatioF()
    beklenen_satir = PARTY_ROW_H * ratio
    check("Parti satir yuksekligi 2 uyelik kayittan turedi",
          abs(calib.party_row_height_exact() - beklenen_satir) <= 1.0,
          "olcek={} row_h={:.1f} beklenen={:.1f}".format(
              ratio, calib.party_row_height_exact(), beklenen_satir))

    # ---------------------------------------------------------------- okuma
    for value in (100, 60, 30, 0):
        dummy.hp_slider.setValue(value)
        pump(app, 0.35)
        read = ctx.bar_percent(CALIB_HP)
        check("HP %{} okundu".format(value), abs(read - value) <= 5,
              "okunan=%.1f" % read)
    dummy.hp_slider.setValue(100)

    dummy.mp_slider.setValue(45)
    pump(app, 0.35)
    read = ctx.bar_percent(CALIB_MP)
    check("MP %45 okundu", abs(read - 45) <= 5, "okunan=%.1f" % read)

    # Gercek oyun hatasinin birebir senaryosu: MP ~%81 (3018/3740) iken eski
    # BGR toleransi koyu mavi bos kismi da sayip %100 gosteriyordu.
    dummy.mp_slider.setValue(81)
    pump(app, 0.35)
    read = ctx.bar_percent(CALIB_MP)
    check("MP %81 okundu (koyu mavi bos kisim tuzagi)", abs(read - 81) <= 5,
          "okunan=%.1f" % read)
    dummy.mp_slider.setValue(100)

    # ---------------------------------------------------------------- parti
    for count in (2, 5, 8):
        dummy.count_spin.setValue(count)
        party.request_rescan()
        pump(app, 0.4)
        party.update(force=True)
        check("Parti uye sayisi {} bulundu".format(count),
              party.member_count() == count,
              "bulunan={}".format(party.member_count()))

    dummy.count_spin.setValue(4)
    dummy.member_sliders[2].setValue(0)
    party.request_rescan()
    pump(app, 0.4)
    party.update(force=True)
    members = party.members()
    check("0%% HP uye BOS satir sayilmadi (tuzak #10)",
          len(members) == 4 and members[2]["present"],
          "uye sayisi={}".format(len(members)))
    check("0%% HP uyenin orani ~0",
          members[2]["percent"] < 5 if len(members) > 2 else False,
          "%.1f" % (members[2]["percent"] if len(members) > 2 else -1))
    dummy.member_sliders[2].setValue(100)
    pump(app, 0.3)

    # ------------------------------------------------- RPR (renk tabanli)
    # Ayrintili el/yon/zemin senaryolari test_rpr.py'de; burada temel akis.
    dummy.left_burnt_check.setChecked(True)
    dummy.right_burnt_check.setChecked(True)
    pump(app, 0.5)
    rpr_rect = global_rect(canvas, RPR_RECT)
    rpr_img = scanner.region(rpr_rect)
    rpr_region = CalibrationRegion(CALIB_RPR, rect=rpr_rect)
    rpr_region.ref_color = vision.vivid_dominant_color(rpr_img)
    rpr_region.ratio_full = max(
        0.002, vision.color_presence_ratio(rpr_img, rpr_region.ref_color)
    )
    rpr_region.saved = True
    calib.save_region(rpr_region)
    check("RPR iki silah yanikken KIRIK okunuyor", ctx.rpr_broken(),
          "oran %{:.1f}".format(ctx.rpr_ratio() * 100))
    dummy.left_burnt_check.setChecked(False)
    pump(app, 0.4)
    check("RPR tek silah yanikken de KIRIK", ctx.rpr_broken(),
          "oran %{:.1f}".format(ctx.rpr_ratio() * 100))
    dummy.right_burnt_check.setChecked(False)
    pump(app, 0.4)
    check("RPR silahlar saglamken saglam", not ctx.rpr_broken(),
          "oran %{:.1f}".format(ctx.rpr_ratio() * 100))

    # ---------------------------------------------------------------- kapilar
    state.master_on.set()
    state.game_focused.set()

    # ---------------------------------------------------------------- pot
    pot = PotModule(ctx)
    pot.set_config({
        "hp": {"enabled": True, "threshold": 50, "key": "1", "fpage": "F2"},
        "mp": {"enabled": True, "threshold": 40, "key": "2", "fpage": NO_PAGE},
        "minor": {"enabled": True, "threshold": 80, "key": "3"},
        "third": {"enabled": False},
    })
    pot.set_enabled(True)
    pot.start()
    dummy.hp_slider.setValue(30)
    dummy.mp_slider.setValue(90)
    pump(app, 2.6)
    pot.set_enabled(False)
    pot.stop()

    hp_presses = [p for p in fake_input.page_keys() if p[1] == "1"]
    minor_presses = [p for p in fake_input.page_keys() if p[1] == "3"]
    mp_presses = [p for p in fake_input.page_keys() if p[1] == "2"]
    check("HP potu esik altinda basildi", len(hp_presses) >= 1,
          "{} kez".format(len(hp_presses)))
    check("HP potu F sayfasiyla gonderildi",
          bool(hp_presses) and hp_presses[0][0] == "F2")
    check("Minor bagimsiz basildi (satirlar bagimsiz)", len(minor_presses) >= 1,
          "{} kez".format(len(minor_presses)))
    check("MP potu esigin ustundeyken basilmadi", len(mp_presses) == 0)
    hp_stamps = [t for t, k, p in fake_input.events
                 if k == "page_key" and p[1] == "1"]
    if len(hp_stamps) >= 2:
        gaps = [(b - a) * 1000 for a, b in zip(hp_stamps, hp_stamps[1:])]
        check("Ayni pot tusu 1320 ms cooldown", min(gaps) >= 1300,
              "en kucuk aralik %.0f ms" % min(gaps))
    else:
        check("Ayni pot tusu 1320 ms cooldown", len(hp_stamps) <= 2,
              "2.6 sn'de {} basim".format(len(hp_stamps)))
    dummy.hp_slider.setValue(100)
    dummy.mp_slider.setValue(100)
    fake_input.clear()

    # ---------------------------------------------------------------- atak
    attack = AttackModule(ctx)
    attack.set_config({
        "skills": [
            {"enabled": True, "key": "4", "fpage": NO_PAGE},
            {"enabled": True, "key": "5", "fpage": NO_PAGE},
            {"enabled": False, "key": "", "fpage": NO_PAGE},
            {"enabled": False, "key": "", "fpage": NO_PAGE},
            {"enabled": False, "key": "", "fpage": NO_PAGE},
        ],
        "delay_ms": 300, "random_enabled": False, "random_max": 0,
        "start_page": "F1", "r_enabled": True,
        "rpr_enabled": False, "no_z_until_dead": False,
    })
    dummy.target_check.setChecked(False)
    pump(app, 0.4)
    attack.set_enabled(True)
    attack.start()
    pump(app, 5.0)

    z_stamps = fake_input.stamps("key", "Z")
    z_gaps = [(b - a) * 1000 for a, b in zip(z_stamps, z_stamps[1:])]
    check("Hedef yokken Z basildi", len(z_stamps) >= 2,
          "{} kez".format(len(z_stamps)))
    check("Z araliklari 789-1437 ms bandinda",
          bool(z_gaps) and all(750 <= g <= 1550 for g in z_gaps),
          "araliklar=" + ", ".join("%.0f" % g for g in z_gaps))
    check("Hedef yokken skill basilmadi",
          not [p for p in fake_input.page_keys() if p[1] in ("4", "5")])
    check("Hedef yokken R basilmadi", not fake_input.stamps("key", "R"))

    fake_input.clear()
    force_foreground(dummy, app)
    dummy.target_check.setChecked(True)
    dummy.target_slider.setValue(100)
    pump(app, 3.0)
    attack.set_enabled(False)
    attack.stop()

    skill_order = [p[1] for p in fake_input.page_keys() if p[1] in ("4", "5")]
    check("Hedef varken skiller sirayla basildi", len(skill_order) >= 3,
          "sira=" + "".join(skill_order))
    check("Skill sirasi 4-5-4-5 seklinde donuyor",
          all(a != b for a, b in zip(skill_order, skill_order[1:])),
          "sira=" + "".join(skill_order))
    r_stamps = fake_input.stamps("key", "R")
    r_gaps = [(b - a) * 1000 for a, b in zip(r_stamps, r_stamps[1:])]
    check("R sabit ~1000 ms araliklarla basildi",
          bool(r_gaps) and all(950 <= g <= 1120 for g in r_gaps),
          "araliklar=" + ", ".join("%.0f" % g for g in r_gaps))
    fake_input.clear()

    # ---------------------------------------------------------------- heal
    heal = HealModule(ctx, party)
    heal.set_config({
        "single": {"enabled": True, "threshold": 70, "key": "6",
                   "fpage": "F3", "party_click": True},
        "party": {"enabled": False},
    })
    dummy.count_spin.setValue(4)
    for i in range(4):
        dummy.member_sliders[i].setValue(100)
    dummy.member_sliders[2].setValue(35)
    force_foreground(dummy, app)
    party.request_rescan()
    pump(app, 0.5)
    heal.set_enabled(True)
    heal.start()
    pump(app, 1.2)
    heal.set_enabled(False)
    heal.stop()

    clicks = fake_input.clicks()
    expected = party.members()[2]["center"] if len(party.members()) > 2 else (0, 0)
    check("Dusuk HP'li uyeye tiklandi", bool(clicks),
          "tiklar={}".format(clicks[:2]))
    if clicks:
        dx = abs(clicks[0][0] - expected[0])
        dy = abs(clicks[0][1] - expected[1])
        check("Tik 3. uyenin satir merkezinde", dx <= 2 and dy <= 2,
              "tik={} beklenen={}".format(clicks[0][:2], expected))
    heal_keys = [p for p in fake_input.page_keys() if p[1] == "6"]
    check("Tiktan sonra heal tusu basildi", bool(heal_keys),
          "{} kez".format(len(heal_keys)))
    check("Uye basina 2000 ms koruma (1.2 sn'de tek basim)",
          len(heal_keys) <= 1, "{} basim".format(len(heal_keys)))
    fake_input.clear()

    # ---------------------------------------------------------------- buff
    buff = BuffModule(ctx)
    buff.set_rows([
        {"enabled": True, "key": "7", "fpage": NO_PAGE, "duration": 1},
        {"enabled": True, "key": "8", "fpage": NO_PAGE, "duration": 3},
    ])
    buff.set_enabled(True)
    buff.start()
    pump(app, 2.4)
    buff.set_enabled(False)
    buff.stop()
    seven = [p for p in fake_input.page_keys() if p[1] == "7"]
    eight = [p for p in fake_input.page_keys() if p[1] == "8"]
    check("Buff sayaclari bagimsiz calisti",
          len(seven) >= 2 and len(eight) == 1,
          "1sn buff={} kez, 3sn buff={} kez".format(len(seven), len(eight)))
    fake_input.clear()

    # ---------------------------------------------------------------- tiklayici
    clicker = ClickerModule(ctx)
    clicker.set_actions([
        click_action(400, 300, "left", 60),
        key_action("space", 60),
        click_action(410, 310, "right", 60),
    ])
    clicker.set_repeat(False)
    clicker.set_enabled(True)
    clicker.start()
    clicker.start_playback()
    pump(app, 1.2)
    clicker.set_enabled(False)
    clicker.stop()
    played_clicks = fake_input.clicks()
    raw_keys = [p for _t, k, p in fake_input.events if k == "raw"]
    check("Tiklayici tik+tus karisik oynatti",
          len(played_clicks) == 2 and raw_keys == ["space"],
          "tik={} tus={}".format(len(played_clicks), raw_keys))
    if len(played_clicks) == 2:
        jitter_ok = (abs(played_clicks[0][0] - 400) <= 3
                     and abs(played_clicks[0][1] - 300) <= 3)
        check("Oynatmada konum sapmasi +-3 px icinde", jitter_ok,
              "ilk tik={}".format(played_clicks[0][:2]))

    # ---------------------------------------------------------------- kapilar
    fake_input.clear()
    state.game_focused.clear()
    pot.set_enabled(True)
    pot.start()
    dummy.hp_slider.setValue(20)
    pump(app, 1.0)
    check("Oyun odakta degilken tus gonderilmedi", not fake_input.events,
          "{} olay".format(len(fake_input.events)))
    state.game_focused.set()
    pump(app, 0.8)
    check("Odak geri gelince tus gonderildi", bool(fake_input.events))
    pot.set_enabled(False)
    pot.stop()

    scanner.stop()
    dummy.close()

    print("\n" + "=" * 60)
    failed = [name for name, ok, _d in RESULTS if not ok]
    print("Toplam {} kontrol, {} basarisiz".format(len(RESULTS), len(failed)))
    for name in failed:
        print("  BASARISIZ: " + name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
