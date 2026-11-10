"""DC koruması testi: gerçek oyun / launcher ekran görüntüleri + yeniden giriş zinciri.

Çevrimdışıdır: pencere açmaz, tuş/tık göndermez. Oyun, launcher, fare ve
zaman SAHTE nesnelerle değiştirilir; dc_guard'ın kararları (nereye tıklar,
hangi sırayla, ne zaman vazgeçer) gerçek ekran görüntüleri üzerinde sınanır.

Senaryolar:
  * normal: DC → Confirm → launcher → START → ID → giriş → OTP bip bip
  * bağlantı yok: START gri → launcher kapat/aç 2 kez → kısa bip bip, dur
  * odak: launcher öne alınamıyor → 2 deneme → kısa bip bip, START'a BASILMAZ
"""

import os
import sys
import tempfile

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PyQt5.QtCore import QCoreApplication          # noqa: E402

from app.services import dc_guard as dg            # noqa: E402
from app.services.template_finder import TemplateFinder  # noqa: E402

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ornekler", "dc")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    line = "[{}] {}{}".format("PASS" if ok else "FAIL", name,
                              ("  -- " + str(detail)) if detail else "")
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode("ascii"))


def img(name):
    image = cv2.imread(os.path.join(D, name))
    assert image is not None, name
    return image


# --------------------------------------------------------------- sahte dünya
class World:
    """Oyun/launcher durumu ve olay kaydı."""

    def __init__(self, start_off_times=0, focus_ok=True):
        self.game = True
        self.screen = "dc"
        self.launcher = None          # None | "on" | "off"
        self.start_off_left = start_off_times
        self.focus_ok = focus_ok
        self.fg = 77
        self.events = []


def build_guard(world, images, folder):
    for name in ("CONFIRM_RETRY_S", "GAME_CLOSE_WAIT_S", "LAUNCHER_WAIT_S",
                 "START_SEARCH_S", "GAME_OPEN_WAIT_S", "AFTER_ENTER_S", "OTP_SEARCH_S",
                 "START_DISABLED_S", "LAUNCHER_REOPEN_WAIT_S"):
        setattr(dg, name, 0.3 if name != "START_SEARCH_S" else 1.5)
    wc = dg.window_capture
    wc.find_game_window = lambda t, own_pid=None: 77 if world.game else None
    wc.is_window_alive = lambda h: world.game
    wc.foreground_window = lambda: world.fg

    def set_fg(hwnd, timeout=0):
        world.events.append(("focus", hwnd))
        if world.focus_ok or hwnd == 77:
            world.fg = hwnd
        return world.fg == hwnd
    wc.set_foreground = set_fg

    class Grabber:
        def __init__(self, provider):
            self.provider = provider

        def grab(self):
            hwnd = self.provider() if callable(self.provider) else self.provider
            if hwnd == 55 and world.launcher:
                return images["launcher_" + world.launcher].copy(), (300, 200)
            if hwnd == 77 and world.game:
                return images[world.screen].copy(), (10, 39)
            return None, (0, 0)

        def close(self):
            pass
    wc.WindowGrabber = Grabber

    class Input:
        def click_direct(self, x, y):
            if world.fg not in (55, 77):
                world.events.append(("click-WRONG-WINDOW", x, y))
                return True
            world.events.append(("click", world.screen if world.fg == 77 else "launcher", x, y))
            if world.fg == 77 and world.screen == "dc":
                world.game = False                      # Confirm oyunu kapatır
            elif world.fg == 55 and world.launcher == "on":
                world.launcher = None
                world.game, world.screen = True, "login"
            return True

    class State:
        def input_allowed(self):
            return True

    class Creds:
        username, password = "u", "p"

        def has_account(self):
            return True

    guard = dg.DcGuard(Input(), State(), Creds(), lambda: "", folder)

    def open_launcher(path):
        world.events.append(("launch",))
        if world.start_off_left > 0:
            world.start_off_left -= 1
            world.launcher = "off"
        else:
            world.launcher = "on"
        return {"pid": 999, "handle": None}

    def close_launcher(proc):
        world.events.append(("close-launcher",))
        world.launcher = None

    guard._open_launcher = open_launcher
    guard._close_launcher = close_launcher
    guard._launcher_hwnd = lambda proc: 55 if world.launcher else None

    def type_login(u, p, hwnd):
        world.events.append(("type", hwnd))
        world.screen = "otp"
    guard.typer.type_login = type_login
    beeps = []
    guard._alarm_async = lambda pattern: beeps.append(pattern)
    guard._beep = lambda pattern: beeps.append(pattern)
    exe = os.path.join(folder, "Launcher.exe")
    open(exe, "w").close()
    guard.set_options(True, True, exe)
    return guard, beeps


def run_chain(world, images):
    folder = tempfile.mkdtemp()
    guard, beeps = build_guard(world, images, folder)
    logs = []
    guard.logLine.connect(logs.append)
    guard._handle_dc(dg.window_capture.WindowGrabber(guard._game_hwnd))
    QCoreApplication.processEvents()
    return [e for e in world.events if e[0] != "focus"], beeps, logs


def main():
    app = QCoreApplication(sys.argv)  # noqa: F841  (sinyaller için)
    dc = img("dc_ekran_1280x800.png")
    dc125 = cv2.resize(dc, None, fx=1.25, fy=1.25, interpolation=cv2.INTER_LINEAR)
    login = img("login_ekrani_kullanici.webp")
    otp = img("otp_ekrani_kullanici.webp")
    l_on = img("launcher_kullanici.webp")
    l_off = img("launcher_baglanti_yok_kullanici.webp")

    # ---------------------------------------------------------- şablonlar
    finder = TemplateFinder()
    for frame, label, k in ((dc, "1280", 1.0), (dc125, "1600 (x1.25, gerçek DPI)", 1.25)):
        check("DC yazısı bulunur: " + label, finder.find(frame, "dc_text", dg.TH_DC) is not None)
        match = finder.find(frame, "dc_confirm", dg.TH_CONFIRM)
        check("Confirm doğru yerde: " + label, match is not None
              and abs(match.center()[0] - 639 * k) < 6 and abs(match.center()[1] - 505 * k) < 6,
              match)
    for frame, label in ((login, "giriş"), (otp, "OTP"), (l_on, "launcher"), (l_off, "launcher gri")):
        check("DC yazısı YOK: " + label, finder.find(frame, "dc_text", dg.TH_DC) is None)
    match = finder.find(login, "login_id", dg.TH_LOGIN)
    point = match.point(*dg.LOGIN_ID_BOX) if match else (0, 0)
    check("ID kutusu tıklama noktası kutunun içinde", 720 < point[0] < 890 and 373 < point[1] < 405,
          point)
    check("ID şablonu OTP ekranında yok", finder.find(otp, "login_id", dg.TH_LOGIN) is None)
    check("OTP ekranı bulunur", finder.find(otp, "otp_text", dg.TH_OTP) is not None)
    check("OTP giriş ekranında yok", finder.find(login, "otp_text", dg.TH_OTP) is None)

    guard_probe = dg.DcGuard.__new__(dg.DcGuard)
    guard_probe.finder = finder
    state_on, m_on = dg.DcGuard._start_state(guard_probe, l_on)
    state_off, m_off = dg.DcGuard._start_state(guard_probe, l_off)
    check("START aktif algılanır", state_on == "on", m_on)
    check("START gri (bağlantı yok) algılanır", state_off == "off", m_off)

    images = {"dc": dc125, "login": login, "otp": otp, "launcher_on": l_on, "launcher_off": l_off}

    # ---------------------------------------------------------- normal
    world = World()
    events, beeps, logs = run_chain(world, images)
    kinds = [e[0] for e in events]
    check("Normal: sıra Confirm → launch → START → ID → yaz",
          kinds == ["click", "launch", "click", "click", "type"], kinds)
    if kinds[:1] == ["click"]:
        check("Normal: Confirm noktası (gerçek testte 809,671)",
              abs(events[0][2] - 809) < 6 and abs(events[0][3] - 671) < 6, events[0])
    if len(events) >= 4:
        check("Normal: START launcher penceresine göre",
              300 + 354 < events[2][2] < 300 + 486 and 200 + 494 < events[2][3] < 200 + 530,
              events[2])
        check("Normal: ID kutusu", 10 + 720 < events[3][2] < 10 + 890
              and 39 + 373 < events[3][3] < 39 + 405, events[3])
    check("Normal: OTP'de bip bip", any(p == [(1200, 160, 0.12), (1200, 160, 0.0)] for p in beeps),
          beeps)
    check("Normal: hata bip'i YOK", dg.FAIL_BEEP not in beeps)

    # ---------------------------------------------------------- bağlantı yok, 2. yeniden açılışta düzelir
    world = World(start_off_times=2)
    events, beeps, logs = run_chain(world, images)
    kinds = [e[0] for e in events]
    check("Bağlantı geri geldi: 2 kapat/aç sonra START",
          kinds == ["click", "launch", "close-launcher", "launch", "close-launcher", "launch",
                    "click", "click", "type"], kinds)
    check("Bağlantı geri geldi: hata bip'i YOK", dg.FAIL_BEEP not in beeps)

    # ---------------------------------------------------------- bağlantı hiç yok
    world = World(start_off_times=99)
    events, beeps, logs = run_chain(world, images)
    kinds = [e[0] for e in events]
    check("Bağlantı yok: en çok 3 açılış (1 + 2 yeniden)", kinds.count("launch") == 3, kinds)
    check("Bağlantı yok: START'a basılmadı", kinds.count("click") == 1, kinds)
    check("Bağlantı yok: kısa bip bip", dg.FAIL_BEEP in beeps, beeps)

    # ---------------------------------------------------------- launcher öne alınamıyor
    world = World(focus_ok=False)
    events, beeps, logs = run_chain(world, images)
    kinds = [e[0] for e in events]
    focus_tries = [e for e in world.events if e == ("focus", 55)]
    check("Odak yok: launcher 2 kez öne alınmaya çalışıldı", len(focus_tries) == 2, focus_tries)
    check("Odak yok: START'a / yanlış pencereye BASILMADI",
          "click-WRONG-WINDOW" not in kinds and kinds.count("click") == 1, kinds)
    check("Odak yok: kısa bip bip", dg.FAIL_BEEP in beeps, beeps)

    print("\n" + "=" * 60)
    failed = [n for n, ok in RESULTS if not ok]
    print("Toplam {} kontrol, {} başarısız".format(len(RESULTS), len(failed)))
    for name in failed:
        print("  BASARISIZ: " + name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
