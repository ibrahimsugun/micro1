"""micro1-master'dan aynen alınan Interception sürücü sarmalayıcısı.

Tek değişiklik: modül içi importlar relative yapıldı.
"""

from .consts import (
    interception_filter_key_state,
    interception_filter_mouse_state,
    interception_key_state,
    interception_mouse_flag,
    interception_mouse_state,
)
from .interception import MAX_DEVICES, MAX_KEYBOARD, MAX_MOUSE, interception
from .stroke import key_stroke, mouse_stroke, stroke

__all__ = [
    "MAX_DEVICES",
    "MAX_KEYBOARD",
    "MAX_MOUSE",
    "interception",
    "interception_filter_key_state",
    "interception_filter_mouse_state",
    "interception_key_state",
    "interception_mouse_flag",
    "interception_mouse_state",
    "key_stroke",
    "mouse_stroke",
    "stroke",
]
