"""Hızlı giriş: kullanıcı adı → ~1 sn → TAB → şifre → ~1 sn → ENTER.

Her karakter insan yazıyormuş gibi gönderilir: tuş basılı kalma süresi,
tuşlar arası aralık ve ara sıra "düşünme" duraklamaları rastgeledir. Büyük
harf / sembol için SHIFT, AltGr sembolleri (Türkçe Q'da @, # ...) için
Ctrl+Alt basılır; Caps Lock açıksa harflerde SHIFT tersine çevrilir.

GÜVENLİK: Şifre YANLIŞ pencereye yazılmasın diye her tuştan önce ön plan
penceresi kontrol edilir; hedef pencere odağı kaybederse dizi anında kesilir.
Panik tuşu da diziyi keser.
"""

import ctypes
import random
import threading
import time

from PyQt5.QtCore import QObject, pyqtSignal

from . import window_capture

# Sabit tarama kodları
SC_TAB = 0x0F
SC_ENTER = 0x1C
SC_LSHIFT = 0x2A
SC_LCTRL = 0x1D
SC_ALT = 0x38          # E0 ile = sağ Alt (AltGr)
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_CAPITAL = 0x14

# "Bir saniye" beklemeleri — insan elinde tam 1000 ms olmaz.
FIELD_WAIT_MIN_S = 0.95
FIELD_WAIT_MAX_S = 1.20

try:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _user32.VkKeyScanExW.restype = ctypes.c_short
    _user32.GetKeyboardLayout.restype = ctypes.c_void_p
    _user32.GetKeyboardLayout.argtypes = [ctypes.c_uint]
    _user32.VkKeyScanExW.argtypes = [ctypes.c_wchar, ctypes.c_void_p]
    _user32.MapVirtualKeyExW.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
    _user32.MapVirtualKeyExW.restype = ctypes.c_uint
    _user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _user32.GetWindowThreadProcessId.restype = ctypes.c_uint
    WINAPI = True
except Exception:                                    # pragma: no cover
    _user32 = None
    WINAPI = False


class LoginAborted(Exception):
    pass


# ------------------------------------------------------------------ zamanlama
def hold_time() -> float:
    """Tuşun basılı kaldığı süre (insan: ~40-110 ms)."""
    return random.uniform(0.040, 0.110)


def gap_time() -> float:
    """İki karakter arası süre.

    Çoğunlukla 90-260 ms arası (gauss), %7 olasılıkla 350-750 ms'lik
    "nerede kalmıştım" duraklaması.
    """
    if random.random() < 0.07:
        return random.uniform(0.35, 0.75)
    return min(0.42, max(0.07, random.gauss(0.16, 0.05)))


def field_wait() -> float:
    return random.uniform(FIELD_WAIT_MIN_S, FIELD_WAIT_MAX_S)


# ------------------------------------------------------------------ harita
def keyboard_layout(hwnd=None):
    if not WINAPI:
        return None
    thread = 0
    if hwnd:
        try:
            thread = _user32.GetWindowThreadProcessId(int(hwnd), None)
        except Exception:
            thread = 0
    return _user32.GetKeyboardLayout(thread)


def caps_lock_on() -> bool:
    if not WINAPI:
        return False
    try:
        return bool(_user32.GetKeyState(VK_CAPITAL) & 1)
    except Exception:
        return False


def map_char(ch: str, layout):
    """Karakter → (scan, vk, shift, altgr) ya da yazılamıyorsa None."""
    if not WINAPI:
        return None
    result = _user32.VkKeyScanExW(ch, layout)
    if result == -1:
        return None
    vk = result & 0xFF
    mods = (result >> 8) & 0xFF
    scan = _user32.MapVirtualKeyExW(vk, 0, layout)     # MAPVK_VK_TO_VSC
    if not scan:
        return None
    shift = bool(mods & 1)
    altgr = bool(mods & 2) and bool(mods & 4)
    if (mods & 2 or mods & 4) and not altgr:
        return None                                      # yalnız Ctrl / yalnız Alt: metin değil
    return scan, vk, shift, altgr


def untypable_chars(text: str, layout=None):
    """Mevcut klavye düzeninde basılamayan karakterler (kayıt anında uyarı için)."""
    if layout is None:
        layout = keyboard_layout()
    return sorted({ch for ch in text or "" if map_char(ch, layout) is None})


# ------------------------------------------------------------------ yazıcı
class LoginTyper(QObject):
    """Giriş dizisini arka plan thread'inde çalıştırır."""

    status = pyqtSignal(str)            # ilerleme metni
    finished = pyqtSignal(bool, str)    # (başarılı mı, mesaj)

    def __init__(self, input_service, app_state, parent=None):
        super().__init__(parent)
        self._input = input_service
        self._state = app_state
        self._thread = None
        self._cancel = threading.Event()

    def busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def cancel(self):
        self._cancel.set()

    def start(self, username: str, password: str, hwnd):
        if self.busy():
            return False
        self._cancel.clear()
        self._thread = threading.Thread(
            target=self._run, args=(username, password, hwnd),
            name="hizli-giris", daemon=True,
        )
        self._thread.start()
        return True

    # ------------------------------------------------------------ iç işler
    def _check(self, hwnd):
        if self._cancel.is_set():
            raise LoginAborted("İptal edildi.")
        if not self._state.input_allowed():
            raise LoginAborted("Panik tuşu: giriş kesildi.")
        if hwnd and window_capture.foreground_window() != int(hwnd):
            raise LoginAborted(
                "Oyun penceresi odağı kaybetti — şifre başka yere yazılmasın "
                "diye giriş durduruldu."
            )

    def _sleep(self, seconds, hwnd):
        end = time.monotonic() + seconds
        while True:
            self._check(hwnd)
            left = end - time.monotonic()
            if left <= 0:
                return
            time.sleep(min(0.03, left))

    def _tap(self, scan, vk, hwnd, extended=False):
        self._check(hwnd)
        self._input.key_event_locked(scan, vk, up=False, extended=extended)
        time.sleep(hold_time())
        self._input.key_event_locked(scan, vk, up=True, extended=extended)

    def _type_char(self, ch, layout, hwnd):
        mapped = map_char(ch, layout)
        if mapped is None:
            raise LoginAborted("'{}' karakteri bu klavye düzeninde yazılamıyor.".format(ch))
        scan, vk, shift, altgr = mapped
        if ch.isalpha() and caps_lock_on():
            shift = not shift
        mods = []
        if altgr:
            mods = [(SC_LCTRL, VK_CONTROL, False), (SC_ALT, VK_MENU, True)]
        elif shift:
            mods = [(SC_LSHIFT, VK_SHIFT, False)]
        self._check(hwnd)
        pressed = []
        try:
            for m_scan, m_vk, m_ext in mods:
                self._input.key_event_locked(m_scan, m_vk, up=False, extended=m_ext)
                pressed.append((m_scan, m_vk, m_ext))
                time.sleep(random.uniform(0.025, 0.070))
            self._tap(scan, vk, hwnd)
            if mods:
                time.sleep(random.uniform(0.015, 0.050))
        finally:
            # Değiştirici tuşlar ne olursa olsun bırakılır (takılı SHIFT kalmasın).
            for m_scan, m_vk, m_ext in reversed(pressed):
                self._input.key_event_locked(m_scan, m_vk, up=True, extended=m_ext)

    def _type_text(self, text, layout, hwnd):
        for index, ch in enumerate(text):
            self._type_char(ch, layout, hwnd)
            if index < len(text) - 1:
                self._sleep(gap_time(), hwnd)

    def _run(self, username, password, hwnd):
        try:
            if hwnd:
                self.status.emit("Oyun penceresi öne alınıyor…")
                if not window_capture.set_foreground(hwnd, timeout=1.0):
                    raise LoginAborted(
                        "Oyun penceresi öne alınamadı. Oyun yönetici olarak "
                        "çalışıyorsa programı da yönetici olarak başlat."
                    )
                time.sleep(random.uniform(0.25, 0.40))
            layout = keyboard_layout(hwnd)
            bad = untypable_chars(username + password, layout)
            if bad:
                raise LoginAborted(
                    "Şu karakterler mevcut klavye düzeninde yazılamıyor: {}".format(
                        " ".join(bad))
                )
            with self._input.exclusive():
                self.status.emit("Kullanıcı adı yazılıyor…")
                self._type_text(username, layout, hwnd)
                self._sleep(field_wait(), hwnd)
                self.status.emit("TAB")
                self._tap(SC_TAB, VK_TAB, hwnd)
                self._sleep(random.uniform(0.25, 0.45), hwnd)
                self.status.emit("Şifre yazılıyor…")
                self._type_text(password, layout, hwnd)
                self._sleep(field_wait(), hwnd)
                self.status.emit("ENTER")
                self._tap(SC_ENTER, VK_RETURN, hwnd)
            self.finished.emit(True, "Giriş bilgileri gönderildi.")
        except LoginAborted as exc:
            self.finished.emit(False, str(exc))
        except Exception as exc:                         # pragma: no cover
            self.finished.emit(False, "Beklenmeyen hata: {}".format(exc))
