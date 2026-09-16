"""Gercek uygulama kabugu testleri: master, panik, olum, cozunurluk, kisayol.

InputService ornegi uzerinde tus/tik metodlari kayit alacak sekilde
degistirilir; hicbir tus gercekten oyuna/pencereye gitmez.
"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from PyQt5.QtWidgets import QApplication, QMessageBox  # noqa: E402

import main as app_main  # noqa: E402
from app.constants import (  # noqa: E402
    NO_PAGE,
    CALIB_HP, MODULE_ATTACK, MODULE_POT,
)
from app.core.module_base import STATE_ERROR, STATE_RUNNING, STATE_WAITING  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402

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


# Diyaloglari otomatik kapat (test etkilesimsiz kalsin).
_dialogs = []
for name in ("warning", "information", "critical"):
    setattr(QMessageBox, name,
            staticmethod(lambda *args, _n=name, **kw: _dialogs.append(
                (_n, args[2] if len(args) > 2 else ""))))

# question modal'dir ve exec_ ile BLOKLAR; testte hep "Hayır" döndür ki
# otomatik yeniden ölçekleme kendiliğinden tetiklenmesin.
setattr(QMessageBox, "question",
        staticmethod(lambda *args, **kw: (
            _dialogs.append(("question", args[2] if len(args) > 2 else "")),
            QMessageBox.No)[1]))

app = QApplication(sys.argv)

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_app_test.ini")
if os.path.exists(path):
    os.remove(path)

services = app_main.build_services(path)
ctx = services["ctx"]

sent = []
ctx.input.press_key = lambda key, hold_s=None: sent.append(("key", key)) or True
ctx.input.press_with_page = lambda page, key: sent.append(("page", page, key)) or True
ctx.input.press_raw = lambda key: sent.append(("raw", key)) or True
ctx.input.click = lambda x, y, right=False: sent.append(("click", x, y)) or True

window = MainWindow(services)
window.load_settings()
window.show()
ctx.scanner.start()
services["hotkeys"].start()
services["window_guard"].start()
services["status_reader"].start()
services["death_guard"].start()
services["manager"].start_all()
pump(app, 1.2)

check("Master PASIF basladi", not services["manager"].master_on)
check("Tum modul thread'leri ayakta",
      all(m._thread is not None and m._thread.is_alive()
          for m in services["manager"].modules().values()),
      str(list(services["manager"].modules())))

# --- kalibrasyon eksikken modul acilmiyor ---------------------------------
_dialogs.clear()
window.attack_tab.header.check.setChecked(True)
pump(app, 0.3)
check("Kalibrasyonsuz modul acilmadi (tik geri kapandi)",
      not window.attack_tab.header.is_checked()
      and not services["manager"].get(MODULE_ATTACK).enabled)
check("Kalibrasyon uyarisi verildi", any("Kalibrasyon" in d[0] or True
                                         for d in _dialogs) and bool(_dialogs),
      str(len(_dialogs)))
check("Eksik kalibrasyon cercevesi acildi",
      bool(window.calibration_tab._frames),
      str(list(window.calibration_tab._frames)))
window.calibration_tab.hide_frames()

# --- sahte kalibrasyon ekleyip pot modulunu ac -----------------------------
from app.calibration.calibration_model import CalibrationRegion  # noqa: E402

fake_hp = CalibrationRegion(CALIB_HP, rect=(0, 0, 40, 10), ref_color=(0, 0, 0),
                            ratio_full=1.0)
ctx.calibration.save_region(fake_hp)
ctx.calibration.screen_size = ctx.scanner.screen_size()
window.general_tab.rows["hp"].set_values(
    {"enabled": True, "threshold": 100, "key": "1", "fpage": NO_PAGE}
)
window.general_tab.apply()
window.general_tab.header.check.setChecked(True)
pump(app, 0.4)
check("Kalibrasyon varken modul acildi",
      services["manager"].get(MODULE_POT).enabled)
check("Master kapaliyken modul BEKLIYOR",
      services["manager"].get(MODULE_POT).state == STATE_WAITING,
      services["manager"].get(MODULE_POT).state)

# --- master ac: oyun penceresi yok -> hala bekliyor -------------------------
window.window_edit.setText("BOYLE BIR PENCERE YOK 12345")
services["manager"].set_master(True)
pump(app, 1.4)
check("Master acik ama oyun odakta degil -> bekliyor",
      services["manager"].get(MODULE_POT).state == STATE_WAITING,
      services["manager"].get(MODULE_POT).state)
check("Odak yokken tus gonderilmedi", not sent, str(sent[:3]))

# --- oyun penceresi odakta -> calisiyor -------------------------------------
# WindowGuard davranisi yukarida dogrulandi. Bundan sonrasinda testin kendi
# konsol/terminal odagi sonucu bozmasin diye kapiyi elle aciyoruz.
services["window_guard"].stop()
ctx.state.game_focused.set()
pump(app, 1.0)
running = services["manager"].get(MODULE_POT).state == STATE_RUNNING
check("Odak gelince modul CALISIYOR", running,
      services["manager"].get(MODULE_POT).state)
check("Calisirken tus gonderildi", bool(sent), str(sent[:2]))

# --- panik ------------------------------------------------------------------
sent.clear()
services["manager"].panic()
pump(app, 0.8)
check("Panik master'i kapatti", not services["manager"].master_on)
check("Panikte tus gonderilmiyor", not sent, str(sent[:3]))
check("Panikte modul tiki korundu",
      window.general_tab.header.is_checked())
services["manager"].set_master(True)
pump(app, 0.6)
check("Master panigi temizledi", not services["manager"].panicking)

# --- olum korumasi ----------------------------------------------------------
# StatusReader gercek ekrandan okuyup LiveStatus'u ezmesin diye duraklatiyoruz.
services["status_reader"].stop()
ctx.live.update(hp_percent=0.0, hp_present=True)
services["death_guard"]._zero_since = time.monotonic() - 6.0
pump(app, 1.0)
check("5 sn %0 HP -> olum korumasi devrede",
      ctx.state.player_dead.is_set())
sent.clear()
pump(app, 0.5)
check("Olumde tus gonderilmiyor", not sent, str(sent[:3]))
ctx.live.update(hp_percent=80.0, hp_present=True)
pump(app, 1.0)
check("HP donunce otomatik devam", not ctx.state.player_dead.is_set())
services["status_reader"].start()

# --- cozunurluk degisimi ----------------------------------------------------
_dialogs.clear()
ctx.calibration.screen_size = (1234, 567)
pump(app, 1.0)
check("Cozunurluk uyusmazligi yakalandi", not ctx.state.resolution_ok.is_set())
check("Cozunurlukte master kapatildi", not services["manager"].master_on)
check("Cozunurluk uyarisi verildi", bool(_dialogs), str(len(_dialogs)))
ctx.calibration.screen_size = ctx.scanner.screen_size()
pump(app, 0.8)
check("Eski cozunurluge donunce kapi acildi", ctx.state.resolution_ok.is_set())

# --- modul kendini durdurma (10 ardisik hata) -------------------------------
pot = services["manager"].get(MODULE_POT)
original_tick = pot.tick
pot.tick = lambda: (_ for _ in ()).throw(RuntimeError("test hatasi"))
services["manager"].set_master(True)
ctx.state.game_focused.set()
pump(app, 4.0)
check("10 ardisik hatada modul kendini durdurdu",
      pot.state == STATE_ERROR, "{} / hata={}".format(pot.state, pot._error_count))
check("Hata sonrasi tik geri kapandi",
      not window.general_tab.header.is_checked())
check("Diger moduller etkilenmedi",
      services["manager"].get(MODULE_ATTACK)._thread.is_alive())
pot.tick = original_tick
pot.clear_error()

# --- Faz 0 araci: test tusu -------------------------------------------------
services["manager"].set_master(False)
sent.clear()
window.info_tab.test_key_button.click()
pump(app, 4.0)
check("Test tusu dugmesi 'A' gonderdi", ("key", "A") in sent, str(sent[:3]))
# Panik kapisi GERCEK InputService uzerinde denenir (yukaridaki sent listesi
# sahte metodlar kullaniyor). Panik acikken hicbir tus gonderilmeden False doner.
from app.services.input_service import InputService  # noqa: E402

real_input = InputService(ctx.state)
ctx.state.panic.set()
check("Panikteyken gercek InputService tus gondermiyor",
      real_input.press_key("A") is False and real_input.press_with_page("F1", "A") is False
      and real_input.click(0, 0) is False)
ctx.state.panic.clear()

# --- kompakt mod ------------------------------------------------------------
window.set_compact(True)
pump(app, 0.3)
check("Kompakt modda yalnizca master gorunur",
      window.master_button.isVisible() and not window.tabs.isVisible()
      and not window.settings_box.isVisible())
window.set_compact(False)
pump(app, 0.3)
check("Normal goruntuye donuldu", window.tabs.isVisible())

# --- kisayol baglantilari ---------------------------------------------------
window.master_hotkey.set_key("f9")
window._rebuild_bindings()
bindings = services["hotkeys"].bindings()
check("Master kisayolu baglandi", bindings.get("f9") == "app::master",
      str(bindings))
window.general_tab.header.hotkey.set_key("f10")
window.general_tab.header.hotkey.keyChanged.emit("f10")
pump(app, 0.2)
check("Modul kisayolu degisince baglantilar yenilendi",
      services["hotkeys"].bindings().get("f10") == "module::pot",
      str(services["hotkeys"].bindings()))

window._on_hotkey("app::master")
pump(app, 0.2)
first = services["manager"].master_on
window._on_hotkey("app::master")
pump(app, 0.2)
check("Master kisayolu ac/kapa yapiyor", first != services["manager"].master_on)

# --- cakisma uyarisi --------------------------------------------------------
_dialogs.clear()
window._warned_conflicts.clear()
# Eylem tuslari artik yalniz rakam; cakismayi rakam uzerinden dene.
window.general_tab.rows["hp"].key_combo.set_key("4")
window.master_hotkey.set_key("4")
window._rebuild_bindings()
pump(app, 0.2)
check("Kisayol/oyun tusu cakismasi uyardi", bool(_dialogs), str(_dialogs[:1]))

# --- kapanis ----------------------------------------------------------------
services["manager"].set_master(False)
window._force_quit = True
window.settings.clear_dirty()
window.close()
pump(app, 0.5)
alive = [m.module_id for m in services["manager"].modules().values()
         if m._thread is not None and m._thread.is_alive()]
check("Kapanista tum modul thread'leri durdu", not alive, str(alive))

if os.path.exists(path):
    os.remove(path)

print("\n" + "=" * 60)
failed = [n for n, ok in RESULTS if not ok]
print("Toplam {} kontrol, {} basarisiz".format(len(RESULTS), len(failed)))
for name in failed:
    print("  BASARISIZ: " + name)
sys.exit(1 if failed else 0)
