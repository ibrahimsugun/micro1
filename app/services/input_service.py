"""Sentetik klavye/fare gönderimi (injection yok, yalnız girdi sürücüsü/API).

Birincil yol: Interception sürücüsü (micro1-master dosyaları aynen).
Yedek yol: PyAutoGUI / win32. Sürücü yoksa sessizce yutulmaz; backend adı
Bilgi sekmesinde gösterilir ve açılışta tek seferlik uyarı verilir.

ARKA PLAN MODU: Ölçüldü ki bu istemci girdiyi YALNIZ odaktayken işliyor —
pencere mesajları (PostMessage/SendMessage) etkisiz, odaksız donanım tuşu da
etkisiz. Bu yüzden gönderim yolu HİÇ DEĞİŞMEZ (aynı Interception/win32 çağrısı,
aynı insansı süreler); yalnızca etrafına kısa bir ODAK DEVRİ sarılır: oyun ~100
ms ön plana alınır, tuş/tık gider, odak önceki pencereye geri verilir. Oyun
zaten ön plandaysa hiçbir şey yapılmaz (ek yük sıfır).

Görüntü okuma arka planda çalıştığı için pencerenin GÖRÜNÜR olması gerekmez;
odak devri yalnız gönderim anını kapsar.
"""

import random
import threading
import time
from contextlib import contextmanager

import pyautogui

from . import window_capture

from ..constants import (
    KEY_HOLD_MAX_MS,
    KEY_HOLD_MIN_MS,
    KEYCODES,
    NO_PAGE,
    PAGE_SWITCH_WAIT_MS,
)

pyautogui.FAILSAFE = False   # köşe istisnası fallback'i kesmesin; güvenlik panik tuşunda
pyautogui.PAUSE = 0.0

try:
    import win32api
    import win32con

    WIN32_AVAILABLE = True
except Exception:                                    # pragma: no cover
    WIN32_AVAILABLE = False

try:
    from .interception_driver import (
        MAX_DEVICES,
        interception,
        interception_key_state,
        key_stroke,
    )

    INTERCEPTION_IMPORTED = True
except Exception:                                    # pragma: no cover
    INTERCEPTION_IMPORTED = False


class InputService:
    """Tüm tuş/tık gönderimi buradan geçer; tek Lock basımı atomik yapar."""

    BACKEND_INTERCEPTION = "Interception"
    BACKEND_FALLBACK = "PyAutoGUI / win32 (yedek)"

    # Odak alindiktan sonra oyunun aktivasyonu isleyip tusu ornekleyebilmesi
    # icin gereken bekleme. Zamanlama taramasinda 50 ms ile 4/4 guvenilir
    # olculdu; daha kisasi iskalanabiliyor. YALNIZ odak YENI alindiginda
    # beklenir; odak zaten bizdeyse hic beklenmez.
    FOCUS_SETTLE_S = 0.05

    def __init__(self, app_state):
        self._state = app_state
        self._lock = threading.Lock()
        self._driver = None
        self._keyboard = None
        self._backend_name = self.BACKEND_FALLBACK
        self._embed_hwnd = None
        self._focus = window_capture.BackgroundFocus()
        self.focus_error = ""
        self.driver_error = ""
        self._init_driver()

    # ------------------------------------------------------------ arka plan
    def set_embed_target(self, hwnd):
        """Arka plan modunda odaklanacak pencere. None = normal mod."""
        new_hwnd = int(hwnd) if hwnd else None
        if new_hwnd is None and self._embed_hwnd is not None:
            self.release_focus()
        self._embed_hwnd = new_hwnd

    def embed_target(self):
        return self._embed_hwnd

    def release_focus(self):
        """Odagi kullanicinin penceresine geri verir (master kapaninca)."""
        try:
            return self._focus.release()
        except Exception:
            return False

    @property
    def backend(self) -> str:
        if self._embed_hwnd:
            return "{} + arka plan odak".format(self._backend_name)
        return self._backend_name

    @backend.setter
    def backend(self, value):
        self._backend_name = value

    @contextmanager
    def _target_focus(self):
        """Arka plan modunda oyunun odakta OLMASINI saglar.

        Oyun zaten odaktaysa hicbir sey yapmaz (hizli yol). Degilse odagi
        ONE CIKARMADAN alir: kullanicinin penceresi gorsel olarak ustte kalir.
        Odak alinamazsa tus GONDERILMEZ - aksi halde kullanicinin yazdigi
        uygulamaya duserdi (olculdu: odaksiz tuslar kullaniciya siziyor).

        Normal modda (hedef yok) hicbir sey yapmaz; mevcut davranis birebir.
        """
        hwnd = self._embed_hwnd
        if not hwnd:
            yield True
            return
        already = window_capture.foreground_window() == hwnd
        ok = self._focus.ensure(hwnd)
        if not ok:
            self.focus_error = (
                "Oyun penceresine odak verilemedi ({}). Oyun yonetici olarak "
                "calisiyorsa programi da yonetici olarak baslat.".format(
                    self._focus.last_error)
            )
        else:
            self.focus_error = ""
            if not already and self.FOCUS_SETTLE_S:
                time.sleep(self.FOCUS_SETTLE_S)   # yalniz YENI alindiysa
        yield ok

    # ------------------------------------------------------------------ kurulum
    def _init_driver(self):
        if not INTERCEPTION_IMPORTED:
            self.driver_error = "interception modülü içe aktarılamadı."
            return
        try:
            driver = interception()
            keyboard = None
            for i in range(MAX_DEVICES):
                # is_keyboard yalnız numara aralığına bakar; cihazın gerçekten
                # AÇILABİLDİĞİNİ de doğrula. Sürücünün fare yarısı kurulu
                # olmayan makinelerde klavye yarısı tek başına çalışır.
                if interception.is_keyboard(i) and driver.is_available(i):
                    keyboard = i
                    break
            if keyboard is None:
                self.driver_error = "Interception klavye cihazı bulunamadı."
                return
            self._driver = driver
            self._keyboard = keyboard
            self.backend = self.BACKEND_INTERCEPTION
        except Exception as exc:
            self.driver_error = f"Interception sürücüsü başlatılamadı: {exc}"

    @property
    def using_interception(self) -> bool:
        return self._driver is not None and self._keyboard is not None

    # ------------------------------------------------------------------ yardımcı
    @staticmethod
    def is_valid_key(key: str) -> bool:
        return bool(key) and key.upper() in KEYCODES

    @staticmethod
    def _hold_seconds() -> float:
        return random.uniform(KEY_HOLD_MIN_MS, KEY_HOLD_MAX_MS) / 1000.0

    # ------------------------------------------------------------------ klavye
    def press_key(self, key: str, hold_s: float = None) -> bool:
        """Tek tuşa insansı sürede basar. Kilit basımı atomik yapar."""
        if not self.is_valid_key(key):
            return False
        if not self._state.input_allowed():
            return False
        with self._lock:
            with self._target_focus() as ready:
                if not ready:
                    return False
                return self._press_locked(key, hold_s)

    def press_with_page(self, page: str, key: str) -> bool:
        """F sayfası → 100 ms → tuş sırasını tek kilit altında yapar.

        Sayfa geri dönüşü YOKTUR (anket kararı).
        """
        if not self.is_valid_key(key):
            return False
        if not self._state.input_allowed():
            return False
        with self._lock:
            # Sayfa + tuş dizisi TEK odak devrinde biter; iki kez öne alınmaz.
            with self._target_focus() as ready:
                if not ready:
                    return False
                if page and page != NO_PAGE and self.is_valid_key(page):
                    if not self._press_locked(page, None):
                        return False
                    time.sleep(PAGE_SWITCH_WAIT_MS / 1000.0)
                    if not self._state.input_allowed():
                        return False
                return self._press_locked(key, None)

    def _press_locked(self, key: str, hold_s) -> bool:
        hold = self._hold_seconds() if hold_s is None else hold_s
        upper = key.upper()
        if self.using_interception:
            code = KEYCODES[upper]
            stroke = key_stroke(code, interception_key_state.INTERCEPTION_KEY_DOWN.value, 0)
            self._driver.send(self._keyboard, stroke)
            time.sleep(hold)
            stroke.state = interception_key_state.INTERCEPTION_KEY_UP.value
            self._driver.send(self._keyboard, stroke)
            return True
        pag_key = upper.lower()
        pyautogui.keyDown(pag_key)
        time.sleep(hold)
        pyautogui.keyUp(pag_key)
        return True

    # -------------------------------------------------- ham tarama kodu (giriş)
    def exclusive(self):
        """Uzun bir diziyi (hızlı giriş) bölünmeden göndermek için kilit.

        Modül thread'leri bu sürede tuş gönderemez; giriş alanına araya
        '1' gibi bir skill tuşu karışmaz.
        """
        return self._lock

    def key_event_locked(self, scan: int, vk: int, up: bool,
                         extended: bool = False) -> bool:
        """Tek bir tuş olayı (bas YA DA bırak). Kilit ÇAĞIRANDA olmalı."""
        if self.using_interception:
            state = (interception_key_state.INTERCEPTION_KEY_UP.value if up
                     else interception_key_state.INTERCEPTION_KEY_DOWN.value)
            if extended:
                state |= interception_key_state.INTERCEPTION_KEY_E0.value
            self._driver.send(self._keyboard, key_stroke(int(scan), state, 0))
            return True
        if WIN32_AVAILABLE:
            flags = 0
            if extended:
                flags |= win32con.KEYEVENTF_EXTENDEDKEY
            if up:
                flags |= win32con.KEYEVENTF_KEYUP
            win32api.keybd_event(int(vk) & 0xFF, int(scan) & 0xFF, flags, 0)
            return True
        return False

    # -------------------------------------------------- serbest tuşlar (tıklayıcı)
    # pynput adları -> pyautogui adları (yalnız farklı olanlar)
    RAW_KEY_ALIASES = {
        "page_up": "pageup", "page_down": "pagedown",
        "ctrl_l": "ctrlleft", "ctrl_r": "ctrlright",
        "alt_l": "altleft", "alt_r": "altright", "alt_gr": "altright",
        "shift_l": "shiftleft", "shift_r": "shiftright",
        "cmd": "win", "cmd_l": "winleft", "cmd_r": "winright",
        "caps_lock": "capslock", "num_lock": "numlock",
        "scroll_lock": "scrolllock", "print_screen": "printscreen",
        "media_volume_up": "volumeup", "media_volume_down": "volumedown",
    }

    def press_raw(self, key_norm: str) -> bool:
        """Tıklayıcı kaydından gelen serbest tuş (harf/rakam dışı olabilir)."""
        if not key_norm or not self._state.input_allowed():
            return False
        upper = key_norm.upper()
        if upper in KEYCODES:
            return self.press_key(upper)
        name = self.RAW_KEY_ALIASES.get(key_norm.lower(), key_norm.lower())
        with self._lock:
            with self._target_focus() as ready:
                if not ready:
                    return False
                try:
                    pyautogui.keyDown(name)
                    time.sleep(self._hold_seconds())
                    pyautogui.keyUp(name)
                    return True
                except Exception:
                    return False

    # ------------------------------------------------------------------ fare
    def click(self, x: int, y: int, right: bool = False) -> bool:
        """Verilen fiziksel piksele tıklar; fare tıklanan yerde KALIR."""
        if not self._state.input_allowed():
            return False
        x, y = int(x), int(y)
        with self._lock:
            with self._target_focus() as ready:
                if not ready:
                    return False
                # Arka plan modunda kullanıcının imleci ışınlanmış halde
                # kalmasın: tıklamadan önceki yere geri koyulur. Normal modda
                # imleç tıklanan yerde KALIR (mevcut davranış korunur).
                restore_to = None
                if self._embed_hwnd and WIN32_AVAILABLE:
                    try:
                        restore_to = win32api.GetCursorPos()
                    except Exception:
                        restore_to = None
                if WIN32_AVAILABLE:
                    down = win32con.MOUSEEVENTF_RIGHTDOWN if right else win32con.MOUSEEVENTF_LEFTDOWN
                    up = win32con.MOUSEEVENTF_RIGHTUP if right else win32con.MOUSEEVENTF_LEFTUP
                    win32api.SetCursorPos((x, y))
                    time.sleep(0.02)
                    win32api.mouse_event(down, x, y, 0, 0)
                    time.sleep(random.uniform(0.03, 0.06))
                    win32api.mouse_event(up, x, y, 0, 0)
                    if restore_to is not None:
                        try:
                            win32api.SetCursorPos(restore_to)
                        except Exception:
                            pass
                    return True
                if right:
                    pyautogui.rightClick(x, y)
                else:
                    pyautogui.click(x, y)
                return True

    def click_direct(self, x: int, y: int) -> bool:
        """Yeniden giriş zinciri için sol tık: odak devri YAPILMAZ.

        Zincir hedef pencereyi kendisi öne alır; arka plan modunun kayıtlı
        HWND'si o sırada ölü olabilir (oyun kapandı), _target_focus'a takılmasın.
        Oyun yönetici olarak çalışıyor ve biz değilsek Windows SetCursorPos'u
        reddeder → False döner (istisna yukarı taşmaz).
        """
        if not self._state.input_allowed():
            return False
        x, y = int(x), int(y)
        with self._lock:
            try:
                if WIN32_AVAILABLE:
                    win32api.SetCursorPos((x, y))
                    time.sleep(random.uniform(0.04, 0.09))
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
                    time.sleep(random.uniform(0.05, 0.11))
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
                    return True
                pyautogui.click(x, y)
                return True
            except Exception:
                return False

    def move_to(self, x: int, y: int) -> bool:
        if not self._state.input_allowed():
            return False
        with self._lock:
            with self._target_focus() as ready:
                if not ready:
                    return False
                if WIN32_AVAILABLE:
                    win32api.SetCursorPos((int(x), int(y)))
                else:
                    pyautogui.moveTo(int(x), int(y))
                return True
