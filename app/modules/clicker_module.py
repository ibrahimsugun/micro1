"""Diğer sekmesi: fare tıklamalarını VE klavye tuşlarını kaydedip oynatır.

mouseRepeater-main portu. Dinleyici olarak GetAsyncKeyState değil pynput.mouse
kullanılır (çift tıklama kaçırmaz). Oynatmada insansılık: konum +-3 px, gecikme
x0.9-1.1.
"""

import random
import time

from PyQt5.QtCore import QObject, pyqtSignal

from ..constants import DEFAULT_LOOP_MS, MODULE_CLICKER
from ..core.module_base import ModuleBase

try:
    from pynput import keyboard as pynput_keyboard
    from pynput import mouse as pynput_mouse

    PYNPUT_AVAILABLE = True
except Exception:                                    # pragma: no cover
    PYNPUT_AVAILABLE = False

POSITION_JITTER_PX = 3
DELAY_JITTER = (0.9, 1.1)
MIN_STEP_S = 0.01


def click_action(x, y, button="left", delay_after=0):
    return {"type": "click", "x": int(x), "y": int(y),
            "button": button, "delay_after": int(delay_after)}


def key_action(key, delay_after=0):
    return {"type": "key", "key": str(key), "delay_after": int(delay_after)}


def describe(action) -> str:
    delay = action.get("delay_after", 0)
    if action.get("type") == "click":
        side = "Sağ tık" if action.get("button") == "right" else "Sol tık"
        return f"{side}  X:{action['x']}  Y:{action['y']}  (+{delay} ms)"
    return f"Tus: {str(action.get('key', '')).upper()}  (+{delay} ms)"


class ClickRecorder(QObject):
    """Global fare + klavye kaydedici. Yalnız kayıt modunda dinler."""

    actionsChanged = pyqtSignal()
    unavailable = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._actions = []
        self._mouse_listener = None
        self._key_listener = None
        self._last_stamp = None
        self._ignored = set()
        self.recording = False

    def set_ignored_keys(self, keys):
        self._ignored = {k.lower() for k in keys if k}

    def actions(self):
        return [dict(a) for a in self._actions]

    def set_actions(self, actions):
        self._actions = [dict(a) for a in (actions or [])]
        self.actionsChanged.emit()

    def clear(self):
        self._actions = []
        self.actionsChanged.emit()

    # ------------------------------------------------------------------ kayit
    def start(self):
        if self.recording:
            return True
        if not PYNPUT_AVAILABLE:
            self.unavailable.emit("pynput yüklenemedi; kayıt yapılamıyor.")
            return False
        self._last_stamp = None
        self.recording = True
        self._mouse_listener = pynput_mouse.Listener(on_click=self._on_click)
        self._mouse_listener.daemon = True
        self._mouse_listener.start()
        self._key_listener = pynput_keyboard.Listener(on_press=self._on_key)
        self._key_listener.daemon = True
        self._key_listener.start()
        return True

    def stop(self):
        self.recording = False
        for listener in (self._mouse_listener, self._key_listener):
            if listener is not None:
                try:
                    listener.stop()
                except Exception:
                    pass
        self._mouse_listener = None
        self._key_listener = None

    def _stamp_delay(self):
        now = time.monotonic()
        if self._last_stamp is None:
            self._last_stamp = now
            return 0
        delay = int((now - self._last_stamp) * 1000.0)
        self._last_stamp = now
        return delay

    def _append(self, action):
        delay = self._stamp_delay()
        if self._actions:
            self._actions[-1]["delay_after"] = delay
        self._actions.append(action)
        self.actionsChanged.emit()

    def _on_click(self, x, y, button, pressed):
        if not self.recording or not pressed:
            return
        side = "right" if getattr(button, "name", "") == "right" else "left"
        self._append(click_action(x, y, side))

    def _on_key(self, key):
        if not self.recording:
            return
        char = getattr(key, "char", None)
        norm = char.lower() if char else (getattr(key, "name", "") or "").lower()
        if not norm or norm in self._ignored:
            return
        self._append(key_action(norm))


class ClickerModule(ModuleBase):
    module_id = MODULE_CLICKER

    playbackFinished = pyqtSignal()
    stepChanged = pyqtSignal(int)

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, DEFAULT_LOOP_MS["clicker"], parent)
        self._actions = []
        self._repeat = True
        self._index = 0
        self._next_at = 0.0
        self._playing = False

    # ------------------------------------------------------------------ ayarlar
    def set_actions(self, actions):
        self._actions = [dict(a) for a in (actions or [])]

    def actions(self):
        return [dict(a) for a in self._actions]

    def set_repeat(self, value):
        self._repeat = bool(value)

    def repeat(self) -> bool:
        return self._repeat

    def required_now(self):
        return []

    @property
    def playing(self) -> bool:
        return self._playing

    # ------------------------------------------------------------------ oynatma
    def start_playback(self):
        if not self._actions:
            return False
        self._index = 0
        self._next_at = time.monotonic()
        self._playing = True
        return True

    def stop_playback(self):
        self._playing = False
        self._index = 0

    def on_activate(self):
        self._playing = False
        self._index = 0

    def on_deactivate(self):
        self._playing = False

    def tick(self):
        if not self._playing:
            return
        now = time.monotonic()
        if now < self._next_at:
            return
        actions = self._actions
        if not actions:
            self._playing = False
            self.playbackFinished.emit()
            return
        if self._index >= len(actions):
            if not self._repeat:
                self._playing = False
                self.playbackFinished.emit()
                return
            self._index = 0

        action = actions[self._index]
        self.stepChanged.emit(self._index)
        self._perform(action)
        self._index += 1

        delay = max(MIN_STEP_S, (action.get("delay_after", 0) / 1000.0))
        self._next_at = time.monotonic() + delay * random.uniform(*DELAY_JITTER)

    def _perform(self, action):
        if action.get("type") == "click":
            x = int(action["x"]) + random.randint(-POSITION_JITTER_PX, POSITION_JITTER_PX)
            y = int(action["y"]) + random.randint(-POSITION_JITTER_PX, POSITION_JITTER_PX)
            self.ctx.input.click(x, y, right=(action.get("button") == "right"))
        else:
            self.ctx.input.press_raw(action.get("key", ""))
