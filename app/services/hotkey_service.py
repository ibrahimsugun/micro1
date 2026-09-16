"""Global kısayol dinleyicisi (pynput) ve tuş yakalama.

Dinleyici kendi thread'inde çalışır; UI'ya yalnız pyqtSignal ile konuşur.
Dinlenebilecek tuşlarda sınır yoktur (herhangi bir tuş); eylem tuşları ise
constants.ACTION_KEYS ile sınırlıdır - çakışma kontrolu bu ikisini karşılaştırır.
"""

from PyQt5.QtCore import QObject, pyqtSignal

try:
    from pynput import keyboard as pynput_keyboard

    PYNPUT_AVAILABLE = True
except Exception:                                    # pragma: no cover
    PYNPUT_AVAILABLE = False


def normalize_key(key) -> str:
    """pynput tuş nesnesini karşılaştırılabilir tek bir metne çevirir."""
    if key is None:
        return ""
    char = getattr(key, "char", None)
    if char:
        return char.lower()
    name = getattr(key, "name", None)
    if name:
        return name.lower()
    vk = getattr(key, "vk", None)
    if vk is not None:
        return "vk%d" % vk
    return str(key).lower()


SPECIAL_NAMES = {
    "ctrl_l": "SOL CTRL", "ctrl_r": "SAĞ CTRL",
    "alt_l": "SOL ALT", "alt_r": "SAĞ ALT", "alt_gr": "ALT GR",
    "shift_l": "SOL SHIFT", "shift_r": "SAĞ SHIFT",
    "space": "BOŞLUK", "esc": "ESC", "enter": "ENTER", "tab": "TAB",
    "backspace": "GERİ SİL", "delete": "DELETE", "insert": "INSERT",
    "home": "HOME", "end": "END", "page_up": "PAGE UP", "page_down": "PAGE DOWN",
    "up": "YUKARI OK", "down": "AŞAĞI OK", "left": "SOL OK", "right": "SAĞ OK",
    "caps_lock": "CAPS LOCK", "print_screen": "PRINT SCREEN", "pause": "PAUSE",
    "num_lock": "NUM LOCK", "scroll_lock": "SCROLL LOCK", "menu": "MENU",
}


def display_name(norm: str) -> str:
    """Kısayol metnini kullanıcıya gösterilecek biçime çevirir."""
    if not norm:
        return "-"
    if norm in SPECIAL_NAMES:
        return SPECIAL_NAMES[norm]
    return norm.upper()


def action_key_conflicts(hotkey_norm: str, action_key: str) -> bool:
    """Kısayol, ayarlı bir skill/pot tuşuyla aynı fiziksel tuş mu?"""
    if not hotkey_norm or not action_key:
        return False
    return hotkey_norm.lower() == action_key.lower()


class HotkeyService(QObject):
    hotkeyPressed = pyqtSignal(str)     # kayit adi (ornek: "master", "pot")
    keyCaptured = pyqtSignal(str, str)  # (yakalama etiketi, normalize tus)
    unavailable = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bindings = {}             # norm tus -> kayit adi
        self._pressed = set()           # klavye auto-repeat bastirma
        self._capture_label = None
        self._listener = None

    def start(self):
        if not PYNPUT_AVAILABLE:
            self.unavailable.emit("pynput yüklenemedi; global kısayollar çalışmayacak.")
            return
        if self._listener is not None:
            return
        self._listener = pynput_keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def set_bindings(self, bindings):
        """{kayıt adı: normalize tuş} - tek referans atamasıyla takas edilir."""
        table = {}
        for name, key in (bindings or {}).items():
            if key:
                table[key.lower()] = name
        self._bindings = table

    def bindings(self):
        return dict(self._bindings)

    def capture_next(self, label: str):
        """Bir sonraki tuş basımını kısayol olarak yakala (tetikleme yapma)."""
        self._capture_label = label

    def cancel_capture(self):
        self._capture_label = None

    def _on_press(self, key):
        norm = normalize_key(key)
        if not norm:
            return
        if self._capture_label is not None:
            label = self._capture_label
            self._capture_label = None
            self.keyCaptured.emit(label, norm)
            return
        if norm in self._pressed:
            return
        self._pressed.add(norm)
        name = self._bindings.get(norm)
        if name:
            self.hotkeyPressed.emit(name)

    def _on_release(self, key):
        self._pressed.discard(normalize_key(key))
