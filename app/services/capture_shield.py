"""Kendi pencerelerimizi ekran yakalamadan gizleme.

Kalibrasyon çerçeveleri ve overlay oyunun üzerinde durur; ekran taramasi bu
pencereleri gorurse renk ölçümü bozulur. Windows 10 2004+ ile gelen
WDA_EXCLUDEFROMCAPTURE penceleri kullanıcıya gösterir ama ekran yakalamadan
tamamen cikarir. Basarisiz olursa cagiran taraf saydam iç alana düşer.
"""

WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011

try:
    import ctypes

    _user32 = ctypes.windll.user32
    AVAILABLE = True
except Exception:                                    # pragma: no cover
    _user32 = None
    AVAILABLE = False


def exclude_from_capture(widget) -> bool:
    """Widget'i ekran yakalamadan cikarir. Basariliysa True."""
    if not AVAILABLE or widget is None:
        return False
    try:
        handle = int(widget.winId())
    except Exception:
        return False
    try:
        return bool(_user32.SetWindowDisplayAffinity(handle, WDA_EXCLUDEFROMCAPTURE))
    except Exception:
        return False


def include_in_capture(widget) -> bool:
    if not AVAILABLE or widget is None:
        return False
    try:
        return bool(_user32.SetWindowDisplayAffinity(int(widget.winId()), WDA_NONE))
    except Exception:
        return False
