"""DC koruması: oyundan düşmeyi algılar, loglar, alarm çalar, yeniden girer.

ALGILAMA: Oyun penceresi ~1,5 sn'de bir yakalanır (arka planda da çalışır) ve
ortadaki "Disconnected from server (x) (y)" yazısı şablonla aranır. Hata
kodları değişse de "Disconnected from" kısmı sabittir.

AKIŞ (tikler Hızlı Giriş sekmesinde):
  DC alarmı  : log + alarm + Confirm'e bas.
               Confirm önce KAYITLI konuma (son bulunduğu yer, pencereye
               oranla) tıklanır; 10 sn sonra çerçeve hâlâ duruyorsa ekranda
               ARANIR ve tekrar tıklanır (en çok 3 tur).
  Yeniden gir: Confirm → oyunun kapanması 10 sn beklenir → kayıtlı Launcher
               açılır → 10 sn → START'a tıklanır → oyunun açılması 1 dk
               beklenir → ID kutusuna tıklanır → hızlı giriş (ID, TAB, şifre,
               ENTER) → 1 sn → OTP ekranı gelince "bip bip" ve BEKLER.

GÜVENLİK: Panik tuşu ve İptal zinciri her adımda keser. Oyun 10 sn içinde
kapanmazsa ikinci bir istemci AÇILMAZ. DC algılanınca master kapatılır ki
modüller launcher'a / giriş ekranına tuş basmasın.
"""

import datetime
import os
import threading
import time

from PyQt5.QtCore import QObject, pyqtSignal

from . import window_capture
from .login_typer import LoginAborted, LoginTyper
from .template_finder import TemplateFinder

try:
    import winsound
except Exception:                                    # pragma: no cover
    winsound = None

try:
    import mss
except Exception:                                    # pragma: no cover
    mss = None

DEFAULT_GAME_TITLE = "Knight OnLine Client"
LOG_FILE = "dc_log.txt"

POLL_S = 1.5
CONFIRM_RETRY_S = 10.0       # çerçeve bu kadar sürede kapanmazsa ara + tekrar tıkla
CONFIRM_ROUNDS = 3
GAME_CLOSE_WAIT_S = 10.0
LAUNCHER_WAIT_S = 10.0
START_SEARCH_S = 30.0        # START düğmesi bu süre içinde aranır
GAME_OPEN_WAIT_S = 60.0
AFTER_ENTER_S = 1.0
OTP_SEARCH_S = 30.0

LAUNCHER_RESTARTS = 2        # START gri kalırsa launcher en çok 2 kez yeniden açılır
LAUNCHER_REOPEN_WAIT_S = 2.0
START_DISABLED_S = 10.0      # START bu kadar süre gri kalırsa "bağlantı yok" sayılır
FOCUS_TRIES = 2              # pencere öne alma denemesi
START_ACTIVE_SAT = 60.0      # START bölgesi ortalama doygunluk: aktif ≈170, gri ≈15

FAIL_BEEP = [(700, 120, 0.10), (700, 120, 0.0)]       # kısa bip bip: zincir durdu

TH_DC = 0.78
TH_START_ANY = 0.70          # aktif ya da gri START (durum doygunlukla ayrılır)
TH_CONFIRM = 0.78
TH_START = 0.78
TH_LOGIN = 0.82
TH_OTP = 0.80

# login_id şablonunda ID kutusunun ortası (şablonun orijinal ölçeğinde)
LOGIN_ID_BOX = (91, 39)


class Cancelled(Exception):
    pass


class DcGuard(QObject):
    logLine = pyqtSignal(str)          # zaman damgalı log satırı
    status = pyqtSignal(str, str)      # (metin, renk anahtarı: ok/warn/err/idle)
    dcDetected = pyqtSignal()          # ana pencere: master'ı kapat
    notify = pyqtSignal(str)           # önemli olay → Telegram bildirimi
    busyChanged = pyqtSignal(bool)
    optionsChanged = pyqtSignal(dict)  # kayıtlı Confirm konumu güncellendi

    def __init__(self, input_service, app_state, credentials, title_provider,
                 log_folder, parent=None):
        super().__init__(parent)
        self._input = input_service
        self._state = app_state
        self._creds = credentials
        self._title_provider = title_provider
        self._log_path = os.path.join(log_folder or ".", LOG_FILE)
        self.finder = TemplateFinder()
        self.typer = LoginTyper(input_service, app_state)

        # GUI thread'i yazar, izleyici thread okur (basit değerler)
        self.alarm_enabled = False
        self.relogin_enabled = False
        self.launcher_path = ""
        self.confirm_pos = None          # (x/genişlik, y/yükseklik)

        self._stop = threading.Event()
        self._cancel = threading.Event()
        self._busy = False
        self._thread = None

    # ------------------------------------------------------------ yaşam
    def start(self):
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="dc-guard", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self.cancel()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def cancel(self):
        """Süren zinciri keser (panik / İptal)."""
        self._cancel.set()
        self.typer.cancel()

    def busy(self) -> bool:
        return self._busy

    def set_options(self, alarm, relogin, launcher_path, confirm_pos=None):
        self.alarm_enabled = bool(alarm)
        self.relogin_enabled = bool(relogin)
        self.launcher_path = launcher_path or ""
        if confirm_pos is not None:
            self.confirm_pos = confirm_pos

    # ------------------------------------------------------------ yardımcı
    def log(self, text):
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = "{}  {}".format(stamp, text)
        try:
            with open(self._log_path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except Exception:
            pass
        self.logLine.emit(line)

    def _set_busy(self, value):
        self._busy = bool(value)
        self.busyChanged.emit(self._busy)

    def _check(self):
        if self._stop.is_set() or self._cancel.is_set():
            raise Cancelled("İptal edildi.")
        if not self._state.input_allowed():
            raise Cancelled("Panik tuşu: zincir durduruldu.")

    def _sleep(self, seconds):
        end = time.monotonic() + seconds
        while True:
            self._check()
            left = end - time.monotonic()
            if left <= 0:
                return
            time.sleep(min(0.1, left))

    def _title(self):
        try:
            title = (self._title_provider() or "").strip()
        except Exception:
            title = ""
        return title or DEFAULT_GAME_TITLE

    def _game_hwnd(self):
        return window_capture.find_game_window(self._title(), own_pid=os.getpid())

    @staticmethod
    def _beep(pattern):
        if winsound is None:
            return
        for freq, dur, pause in pattern:
            try:
                winsound.Beep(int(freq), int(dur))
            except Exception:
                pass
            time.sleep(pause)

    def _alarm_async(self, pattern):
        threading.Thread(target=self._beep, args=(pattern,), daemon=True).start()

    def _click(self, x, y, what):
        if not self._input.click_direct(x, y):
            raise LoginAborted(
                "{} tıklanamadı. Oyun yönetici olarak çalışıyorsa bu programı da "
                "YÖNETİCİ olarak başlat.".format(what))

    # ------------------------------------------------------------ izleme döngüsü
    def _loop(self):
        grabber = window_capture.WindowGrabber(self._game_hwnd)
        try:
            while not self._stop.is_set():
                if self.alarm_enabled or self.relogin_enabled:
                    try:
                        frame, origin = grabber.grab()
                        if frame is not None and self.finder.find(frame, "dc_text", TH_DC):
                            self._handle_dc(grabber)
                    except Exception as exc:                 # izleme asla ölmesin
                        self.log("İzleme hatası: {}".format(exc))
                        self._stop.wait(5.0)
                self._stop.wait(POLL_S)
        finally:
            grabber.close()

    def relogin_now(self):
        """Elle tetikleme: DC beklemeden yeniden giriş zincirini başlatır.

        Oyun açıksa önce kapanması beklenir (10 sn), kapanmazsa iptal edilir —
        yani açık bir oyunun üstüne ikinci istemci asla açılmaz.
        """
        if self._busy:
            return False
        threading.Thread(target=self._manual_relogin, name="relogin-now",
                         daemon=True).start()
        return True

    def _manual_relogin(self):
        self._cancel.clear()
        self._set_busy(True)
        try:
            self.log("Yeniden giriş elle başlatıldı.")
            self._relogin()
        except Cancelled as exc:
            self.log("Zincir durdu: {}".format(exc))
            self.status.emit(str(exc), "idle")
            self.notify.emit("⏹ Zincir durdu: {}".format(exc))
        except LoginAborted as exc:
            self.log("HATA: {}".format(exc))
            self.status.emit(str(exc), "err")
            self.notify.emit("❌ {}".format(exc))
            self._alarm_async(FAIL_BEEP)
        except Exception as exc:                             # pragma: no cover
            self.log("Beklenmeyen hata: {}".format(exc))
            self.status.emit("Beklenmeyen hata: {}".format(exc), "err")
        finally:
            self._set_busy(False)

    # ------------------------------------------------------------ DC zinciri
    def _handle_dc(self, grabber):
        self._cancel.clear()
        self._set_busy(True)
        relogin = self.relogin_enabled
        try:
            self.log("DC: karakter oyundan düştü (Disconnected from server).")
            self.notify.emit("⚠️ DC: karakter oyundan düştü.{}".format(
                " Yeniden giriş başlıyor…" if relogin else ""))
            self.dcDetected.emit()
            self.status.emit("DC algılandı!", "err")
            if self.alarm_enabled:
                self._alarm_async([(880, 350, 0.12), (660, 350, 0.12)] * 3)
            self._press_confirm(grabber)
            if relogin:
                self._relogin()
            else:
                self.status.emit("DC sonrası Confirm'e basıldı.", "warn")
                self.notify.emit("Confirm'e basıldı (yeniden giriş kapalı).")
        except Cancelled as exc:
            self.log("Zincir durdu: {}".format(exc))
            self.status.emit(str(exc), "idle")
            self.notify.emit("⏹ Zincir durdu: {}".format(exc))
        except LoginAborted as exc:
            self.log("HATA: {}".format(exc))
            self.status.emit(str(exc), "err")
            self.notify.emit("❌ {}".format(exc))
            self._alarm_async(FAIL_BEEP)
        except Exception as exc:                             # pragma: no cover
            self.log("Beklenmeyen hata: {}".format(exc))
            self.status.emit("Beklenmeyen hata: {}".format(exc), "err")
        finally:
            # Aynı çerçeve hâlâ ekrandaysa döngü onu hemen tekrar yakalamasın
            self._stop.wait(3.0)
            self._set_busy(False)

    def _dialog_state(self, grabber):
        """('closed' | 'gone' | 'present', frame, origin)"""
        hwnd = self._game_hwnd()
        if not hwnd or not window_capture.is_window_alive(hwnd):
            return "closed", None, (0, 0)
        frame, origin = grabber.grab()
        if frame is None:
            return "present", None, origin      # okunamadı: kapanmış sayma
        if self.finder.find(frame, "dc_text", TH_DC) is None:
            return "gone", frame, origin
        return "present", frame, origin

    def _press_confirm(self, grabber):
        for round_no in range(1, CONFIRM_ROUNDS + 1):
            self._check()
            hwnd = self._game_hwnd()
            if not hwnd:
                return
            window_capture.set_foreground(hwnd, timeout=1.0)
            frame, origin = grabber.grab()
            if frame is None:
                raise LoginAborted("Oyun görüntüsü alınamadı.")
            h, w = frame.shape[:2]
            point, how = None, ""
            if round_no == 1 and self.confirm_pos:
                point = (int(self.confirm_pos[0] * w), int(self.confirm_pos[1] * h))
                how = "kayıtlı konum"
            else:
                match = self.finder.find(frame, "dc_confirm", TH_CONFIRM)
                if match is not None:
                    point = match.center()
                    how = "arandı ({:.2f})".format(match.score)
                    self.confirm_pos = (point[0] / float(w), point[1] / float(h))
                    self.optionsChanged.emit({"confirm_pos": list(self.confirm_pos)})
            if point is None:
                self.log("Confirm düğmesi bulunamadı (tur {}).".format(round_no))
            else:
                self._click(origin[0] + point[0], origin[1] + point[1], "Confirm")
                self.log("Confirm'e tıklandı ({}, tur {}).".format(how, round_no))

            # Çerçeve kapanana / oyun kapanana kadar en çok 10 sn bekle
            end = time.monotonic() + CONFIRM_RETRY_S
            while time.monotonic() < end:
                self._sleep(0.5)
                state, _f, _o = self._dialog_state(grabber)
                if state in ("closed", "gone"):
                    self.log("DC çerçevesi kapandı ({}).".format(
                        "oyun kapandı" if state == "closed" else "çerçeve gitti"))
                    return
            self.log("10 sn geçti, çerçeve hâlâ ekranda — düğme aranıp tekrar denenecek.")
        raise LoginAborted("Confirm {} denemede kapatılamadı.".format(CONFIRM_ROUNDS))

    def _relogin(self):
        creds = self._creds
        if not creds.has_account():
            raise LoginAborted("Yeniden giriş: kayıtlı hesap yok.")
        path = self.launcher_path
        if not path or not os.path.isfile(path):
            raise LoginAborted("Yeniden giriş: Launcher yolu geçersiz ({}).".format(path or "boş"))

        # 1) oyunun kapanmasını bekle (Confirm çerçeveyi kapatınca oyun kapanıyor)
        self.status.emit("Oyunun kapanması bekleniyor…", "warn")
        end = time.monotonic() + GAME_CLOSE_WAIT_S
        while self._game_hwnd():
            if time.monotonic() >= end:
                raise LoginAborted(
                    "Oyun 10 sn içinde kapanmadı — ikinci istemci açılmasın diye "
                    "yeniden giriş iptal edildi.")
            self._sleep(0.5)
        self.log("Oyun kapandı.")

        # 2-3) launcher → START (bağlantı yoksa launcher yeniden başlatılır)
        self._launch_and_start(path)

        # 4) oyun + giriş ekranı (en çok 1 dk)
        self.status.emit("Oyunun açılması bekleniyor (1 dk)…", "warn")
        hwnd, match, origin = self._wait_login_screen(GAME_OPEN_WAIT_S)
        if match is None:
            raise LoginAborted("Oyun 1 dk içinde giriş ekranına gelmedi.")
        self.log("Giriş ekranı açıldı.")

        # 5) ID kutusuna tıkla, hızlı giriş
        self._bring_front(hwnd, "Oyun penceresi")
        self._sleep(0.4)
        frame, origin = self._grab_window(hwnd)
        fresh = self.finder.find(frame, "login_id", TH_LOGIN)
        if fresh is not None:          # öne alınırken pencere kaydıysa güncel konum
            match = fresh
        self._bring_front(hwnd, "Oyun penceresi")
        bx, by = match.point(*LOGIN_ID_BOX)
        self._click(origin[0] + bx, origin[1] + by, "ID kutusu")
        self.log("ID kutusuna tıklandı.")
        self._sleep(0.5)
        self.status.emit("Hızlı giriş yazılıyor…", "warn")
        self.typer._cancel.clear()
        self.typer.type_login(creds.username, creds.password, hwnd)
        self.log("Kullanıcı adı / şifre gönderildi.")
        self._sleep(AFTER_ENTER_S)

        # 6) OTP ekranı → bip bip ve bekle
        self.status.emit("OTP ekranı bekleniyor…", "warn")
        if self._wait_in_game("otp_text", TH_OTP, OTP_SEARCH_S):
            self.log("OTP ekranı geldi — OTP girmen bekleniyor.")
            self.notify.emit("🔐 Giriş yapıldı, OTP ekranı açık — OTP girmen bekleniyor.")
            self._beep([(1200, 160, 0.12), (1200, 160, 0.0)])
            self.status.emit("OTP ekranında — OTP'yi gir.", "ok")
        else:
            self.log("OTP ekranı {} sn içinde görülmedi.".format(int(OTP_SEARCH_S)))
            self.notify.emit("ℹ️ Giriş bilgileri gönderildi ama OTP ekranı görülmedi.")
            self.status.emit("Giriş gönderildi; OTP ekranı görülmedi.", "warn")

    # ------------------------------------------------------------ launcher
    def _launch_and_start(self, path):
        """Launcher'ı aç, START'a bas. START gri kalırsa (bağlantı yok) launcher
        kapatılıp 2 sn sonra yeniden açılır — en çok LAUNCHER_RESTARTS kez."""
        for attempt in range(LAUNCHER_RESTARTS + 1):
            self._check()
            if attempt:
                self.status.emit("Launcher yeniden açılıyor ({}/{})…".format(
                    attempt, LAUNCHER_RESTARTS), "warn")
            else:
                self.status.emit("Launcher açılıyor…", "warn")
            proc = self._open_launcher(path)
            self.log("Launcher açıldı: {}".format(path))
            self._sleep(LAUNCHER_WAIT_S)
            self.status.emit("START düğmesi aranıyor…", "warn")
            if self._press_start(proc) == "clicked":
                return
            if attempt < LAUNCHER_RESTARTS:
                self.notify.emit("🌐 START basılamıyor (bağlantı yok?) — launcher "
                                 "yeniden açılıyor ({}/{}).".format(attempt + 1, LAUNCHER_RESTARTS))
                self.log("START basılamıyor (giriş sunucusuna bağlanılamadı?) — "
                         "launcher kapatılıp yeniden açılacak ({}/{}).".format(
                             attempt + 1, LAUNCHER_RESTARTS))
            self._close_launcher(proc)
            if attempt < LAUNCHER_RESTARTS:
                self._sleep(LAUNCHER_REOPEN_WAIT_S)
        raise LoginAborted(
            "START {} denemede de basılabilir olmadı (internet / giriş sunucusu "
            "yok?). Yeniden giriş durduruldu.".format(LAUNCHER_RESTARTS + 1))

    def _open_launcher(self, path):
        """Launcher'ı başlatır → {'pid', 'handle', 'before'}.

        'before': açılıştan ÖNCEKİ görünür pencereler. Launcher kendini başka
        süreçle yeniden başlatırsa (güncelleyici, Win11 Notepad'deki gibi)
        PID'den pencere bulunamaz; o zaman YENİ açılan pencerelerin içinde
        START aranır (arkada kalmış pencere de yakalanabilir).
        """
        folder = os.path.dirname(path)
        before = set(self._visible_windows())
        try:
            from win32com.shell import shell, shellcon
            import win32process

            info = shell.ShellExecuteEx(
                fMask=shellcon.SEE_MASK_NOCLOSEPROCESS, lpVerb="open",
                lpFile=path, lpDirectory=folder, nShow=1)
            handle = info.get("hProcess")
            pid = win32process.GetProcessId(handle) if handle else None
            return {"pid": pid, "handle": handle, "before": before}
        except ImportError:
            pass
        except Exception as exc:
            raise LoginAborted("Launcher açılamadı: {}".format(exc))
        try:
            os.startfile(path, cwd=folder)
        except Exception as exc:
            raise LoginAborted("Launcher açılamadı: {}".format(exc))
        return {"pid": None, "handle": None, "before": before}

    @staticmethod
    def _visible_windows():
        """Görünür, makul boyutlu üst düzey pencereler (hwnd listesi)."""
        try:
            import win32gui
        except Exception:
            return []
        found = []

        def callback(hwnd, _):
            try:
                if win32gui.IsWindowVisible(hwnd):
                    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                    if right - left >= 200 and bottom - top >= 150:
                        found.append(hwnd)
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception:
            return []
        return found

    @staticmethod
    def _windows_of_pid(pid):
        """pid'e ait görünür üst düzey pencereler (başlıksız olanlar dahil),
        büyükten küçüğe."""
        if not pid:
            return []
        try:
            import win32gui
            import win32process
        except Exception:
            return []
        found = []

        def callback(hwnd, _):
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                if win32process.GetWindowThreadProcessId(hwnd)[1] != pid:
                    return True
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                if right - left >= 200 and bottom - top >= 150:
                    found.append(((right - left) * (bottom - top), hwnd))
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception:
            return []
        return [hwnd for _area, hwnd in sorted(found, reverse=True)]

    def _launcher_hwnd(self, proc):
        """Önce süreçten bul; olmazsa ekranda START arayıp altındaki pencereyi al
        (launcher kendini başka süreçle yeniden başlatmış olabilir)."""
        windows = self._windows_of_pid(proc.get("pid"))
        if windows:
            return windows[0]
        before = proc.get("before") or set()
        for hwnd in self._visible_windows():
            if hwnd in before or window_capture.window_pid(hwnd) == os.getpid():
                continue
            frame, _origin = self._grab_window(hwnd)
            if frame is not None and self._start_state(frame)[0] is not None:
                proc["pid"] = window_capture.window_pid(hwnd) or proc.get("pid")
                return hwnd
        try:
            match, origin = self._search_screen_once(("launcher_start", "launcher_start_off"))
        except Exception:
            match = None
        if match is None:
            return None
        cx, cy = match.center()
        try:
            import win32gui

            hwnd = win32gui.WindowFromPoint((origin[0] + cx, origin[1] + cy))
            root = win32gui.GetAncestor(hwnd, 2)          # GA_ROOT
            proc["pid"] = window_capture.window_pid(root) or proc.get("pid")
            return root
        except Exception:
            return None

    def _start_state(self, frame):
        """('on' | 'off' | None, Match). Gri/aktif ayrımı renk doygunluğuyla:
        aktif START eflatun (S≈170), basılamaz START gri (S≈15)."""
        on = self.finder.find(frame, "launcher_start", TH_START_ANY)
        off = self.finder.find(frame, "launcher_start_off", TH_START_ANY)
        candidates = [m for m in (on, off) if m is not None]
        if not candidates:
            return None, None
        match = max(candidates, key=lambda m: m.score)
        region = frame[match.y:match.y + match.h, match.x:match.x + match.w]
        if region.size == 0:
            return None, None
        import cv2

        saturation = float(cv2.cvtColor(region[:, :, :3], cv2.COLOR_BGR2HSV)[:, :, 1].mean())
        return ("on" if saturation >= START_ACTIVE_SAT else "off"), match

    def _grab_window(self, hwnd):
        grabber = window_capture.WindowGrabber(hwnd)
        try:
            return grabber.grab()
        finally:
            grabber.close()

    def _press_start(self, proc):
        """'clicked' ya da 'disabled'. Pencere/düğme hiç bulunamazsa LoginAborted."""
        end = time.monotonic() + START_SEARCH_S
        disabled_since = None
        seen_window = False
        while True:
            self._check()
            hwnd = self._launcher_hwnd(proc)
            if hwnd:
                seen_window = True
                frame, _origin = self._grab_window(hwnd)
                state, _match = self._start_state(frame)
                if state == "on":
                    self._bring_front(hwnd, "Launcher")
                    # Öne aldıktan sonra konumu TAZE oku ve hemen bas
                    frame, origin = self._grab_window(hwnd)
                    state, match = self._start_state(frame)
                    if state == "on":
                        self._bring_front(hwnd, "Launcher")
                        cx, cy = match.center()
                        self._click(origin[0] + cx, origin[1] + cy, "START")
                        self.log("START'a tıklandı ({:.2f}).".format(match.score))
                        return "clicked"
                if state == "off":
                    if disabled_since is None:
                        disabled_since = time.monotonic()
                        self.log("START gri (basılamıyor) — bekleniyor.")
                    elif time.monotonic() - disabled_since >= START_DISABLED_S:
                        return "disabled"
                else:
                    disabled_since = None
            if time.monotonic() >= end:
                if disabled_since is not None:
                    return "disabled"
                raise LoginAborted(
                    "Launcher'da START düğmesi bulunamadı." if seen_window
                    else "Launcher penceresi bulunamadı.")
            self._sleep(1.0)

    def _close_launcher(self, proc):
        windows = self._windows_of_pid(proc.get("pid"))
        try:
            import win32con
            import win32gui

            for hwnd in windows:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        except Exception:
            pass
        end = time.monotonic() + 3.0
        while time.monotonic() < end and self._windows_of_pid(proc.get("pid")):
            time.sleep(0.2)
        if self._windows_of_pid(proc.get("pid")):
            self._terminate(proc)
        self.log("Launcher kapatıldı.")

    @staticmethod
    def _terminate(proc):
        try:
            import win32api
            import win32con

            # pid, launcher başka süreçle yeniden başladıysa GÜNCEL süreçtir
            handle = None
            if proc.get("pid"):
                handle = win32api.OpenProcess(win32con.PROCESS_TERMINATE, False, proc["pid"])
            handle = handle or proc.get("handle")
            if handle:
                win32api.TerminateProcess(handle, 1)
        except Exception:
            pass

    # ------------------------------------------------------------ odak
    def _bring_front(self, hwnd, what):
        """Pencere önde değilse öne almayı FOCUS_TRIES kez dener; olmazsa kısa
        bip bip ve zincir durur (başka pencereye tıklanmasın)."""
        for attempt in range(1, FOCUS_TRIES + 1):
            self._check()
            if window_capture.foreground_window() == int(hwnd):
                return
            window_capture.set_foreground(hwnd, timeout=1.0)
            time.sleep(0.25)
            if window_capture.foreground_window() == int(hwnd):
                if attempt > 1:
                    self.log("{} öne alındı.".format(what))
                return
            self.log("{} öne alınamadı ({}/{}).".format(what, attempt, FOCUS_TRIES))
        raise LoginAborted(
            "{} {} denemede öne alınamadı — yanlış pencereye tıklanmasın diye "
            "durduruldu.".format(what, FOCUS_TRIES))

    # ------------------------------------------------------------ arama
    def _search_screen_once(self, names):
        """Tüm masaüstünde tek kare: verilen şablonlardan en iyi eşleşme."""
        if mss is None:
            return None, None
        import numpy as np

        with mss.mss() as sct:
            mon = sct.monitors[0]
            shot = np.ascontiguousarray(np.asarray(sct.grab(mon))[:, :, :3])
        best = None
        for name in names:
            match = self.finder.find(shot, name, TH_START_ANY)
            if match is not None and (best is None or match.score > best.score):
                best = match
        return best, (mon["left"], mon["top"])

    def _wait_login_screen(self, timeout):
        end = time.monotonic() + timeout
        grabber = window_capture.WindowGrabber(self._game_hwnd)
        try:
            while True:
                self._check()
                hwnd = self._game_hwnd()
                if hwnd:
                    frame, origin = grabber.grab()
                    match = self.finder.find(frame, "login_id", TH_LOGIN)
                    if match is not None:
                        return hwnd, match, origin
                if time.monotonic() >= end:
                    return None, None, None
                self._sleep(1.0)
        finally:
            grabber.close()

    def _wait_in_game(self, name, threshold, timeout):
        end = time.monotonic() + timeout
        grabber = window_capture.WindowGrabber(self._game_hwnd)
        try:
            while True:
                self._check()
                frame, _origin = grabber.grab()
                if self.finder.find(frame, name, threshold) is not None:
                    return True
                if time.monotonic() >= end:
                    return False
                self._sleep(0.7)
        finally:
            grabber.close()
