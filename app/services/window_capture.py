"""Pencere bazli yakalama - arka plan (embed) modu.

Ekrani DEGIL pencereyi okur: hedef pencere baska pencerelerin ARKASINDAYKEN de
icerigi alinabilir. Boylece oyunun surekli on planda olma zorunlulugu kalkar.

Tuzak #1: PrintWindow'un cizdigi bitmap GetWindowRect uzayindadir; DWM'in
"genisletilmis cerceve sinirlari" (DWMWA_EXTENDED_FRAME_BOUNDS) ile
karistirilirsa gorunmez kenarlik kadar (~7 px) kayar ve TUM kalibrasyon
dikdortgenleri yanlis yeri okur. Bu yuzden disariya HER ZAMAN client alani ve
client origin'i verilir; ScreenScanner.region() hic degismeden calisir.

Tuzak #2: GDI nesneleri (DC, bitmap) olusturuldugu thread'te kullanilip yine
orada serbest birakilmalidir. WindowGrabber yalniz tarayici thread'inde yasar
(mss ornegiyle ayni kural).

Tuzak #3: ctypes'ta handle donduren fonksiyonlarin restype'i AYARLANMAZSA
64-bit'te handle kirpilir ve sessizce bozuk calisir; asagida hepsi acikca
tanimlidir.
"""

import ctypes
import os
import time
from ctypes import wintypes

import numpy as np

try:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    WINAPI_AVAILABLE = True
except Exception:                                    # pragma: no cover
    user32 = None
    gdi32 = None
    WINAPI_AVAILABLE = False

try:
    dwmapi = ctypes.WinDLL("dwmapi")
except Exception:                                    # pragma: no cover
    dwmapi = None

try:
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    _kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    _kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    _advapi32.OpenProcessToken.restype = wintypes.BOOL
    _advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD)]
    _advapi32.GetTokenInformation.restype = wintypes.BOOL
except Exception:                                    # pragma: no cover
    _kernel32 = None
    _advapi32 = None

# ---------------------------------------------------------------- sabitler
PW_CLIENTONLY = 0x1
PW_RENDERFULLCONTENT = 0x2          # Win 8.1+: DWM icerigi de cizilir (DirectX)
SW_SHOWNOACTIVATE = 4
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
BI_RGB = 0
DWMWA_CLOAKED = 14

# --- pencere mesajlari (arka plan girdi) ---
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002
MAPVK_VK_TO_VSC = 0
MAPVK_VSC_TO_VK_EX = 3
KF_EXTENDED = 0x0100
HWND_TOP = 0
HWND_BOTTOM = 1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010

DPI_AWARENESS_CONTEXT_UNAWARE = ctypes.c_void_p(-1)

# Yakalama varyantlari
GRAB_CLIENT = "client"      # PrintWindow(PW_CLIENTONLY|PW_RENDERFULLCONTENT)
GRAB_WINDOW = "window"      # PrintWindow(PW_RENDERFULLCONTENT) + client kirpma
GRAB_CLIENT0 = "client0"    # PrintWindow(PW_CLIENTONLY) - eski istemciler icin
GRAB_WINDOW0 = "window0"    # PrintWindow(0) - eski istemciler icin
GRAB_BITBLT = "bitblt"      # GetWindowDC + BitBlt (DWM yonlendirme yuzeyi)
GRAB_AUTO = "auto"          # sirayla dener, calisani hatirlar

GRAB_MODES = (GRAB_CLIENT, GRAB_WINDOW, GRAB_CLIENT0, GRAB_WINDOW0, GRAB_BITBLT)

# AUTO sirasi: once PrintWindow (DWM icerigini de cizer), sonra BitBlt.
# Knight Online istemcisi PrintWindow'a HIC yanit vermiyor (Faz 0 olcumu);
# BitBlt ise DWM yonlendirme yuzeyinden okudugu icin pencere ortuluyken de
# dogru kareyi veriyor. Sira bu yuzden BitBlt'i de kapsar.
GRAB_ORDER = (GRAB_CLIENT, GRAB_WINDOW, GRAB_BITBLT, GRAB_CLIENT0, GRAB_WINDOW0)

# Client alani cizen varyantlar (kirpma gerekmez)
_CLIENT_MODES = (GRAB_CLIENT, GRAB_CLIENT0, GRAB_BITBLT)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


if WINAPI_AVAILABLE:                                 # pragma: no branch
    WNDENUMPROC = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
    )

    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetClientRect.restype = wintypes.BOOL
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.ClientToScreen.restype = wintypes.BOOL
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindowDC.argtypes = [wintypes.HWND]
    user32.GetWindowDC.restype = wintypes.HDC
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.ReleaseDC.restype = ctypes.c_int
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    user32.PrintWindow.restype = wintypes.BOOL

    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.DeleteDC.restype = wintypes.BOOL
    gdi32.BitBlt.argtypes = [
        wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD,
    ]
    gdi32.BitBlt.restype = wintypes.BOOL
    gdi32.GetDIBits.argtypes = [
        wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
        ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
    ]
    gdi32.GetDIBits.restype = ctypes.c_int

    user32.PostMessageW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
    ]
    user32.PostMessageW.restype = wintypes.BOOL
    user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    user32.MapVirtualKeyW.restype = wintypes.UINT
    user32.RealChildWindowFromPoint.argtypes = [wintypes.HWND, wintypes.POINT]
    user32.RealChildWindowFromPoint.restype = wintypes.HWND
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD,
                                         wintypes.BOOL]
    user32.AttachThreadInput.restype = wintypes.BOOL
    user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
    user32.AllowSetForegroundWindow.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.BringWindowToTop.restype = wintypes.BOOL
    user32.SetFocus.argtypes = [wintypes.HWND]
    user32.SetFocus.restype = wintypes.HWND
    user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SetWindowPos.restype = wintypes.BOOL
    if hasattr(user32, "GetDpiForWindow"):
        user32.GetDpiForWindow.argtypes = [wintypes.HWND]
        user32.GetDpiForWindow.restype = wintypes.UINT


# ---------------------------------------------------------------- pencere bilgisi
def window_title(hwnd) -> str:
    if not WINAPI_AVAILABLE or not hwnd:
        return ""
    try:
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value or ""
    except Exception:
        return ""


def window_class(hwnd) -> str:
    if not WINAPI_AVAILABLE or not hwnd:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buffer, 256)
        return buffer.value or ""
    except Exception:
        return ""


def window_pid(hwnd) -> int:
    if not WINAPI_AVAILABLE or not hwnd:
        return 0
    try:
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value)
    except Exception:
        return 0


def is_window_alive(hwnd) -> bool:
    if not WINAPI_AVAILABLE or not hwnd:
        return False
    try:
        return bool(user32.IsWindow(hwnd))
    except Exception:
        return False


def is_window_visible(hwnd) -> bool:
    if not WINAPI_AVAILABLE or not hwnd:
        return False
    try:
        return bool(user32.IsWindowVisible(hwnd))
    except Exception:
        return False


def is_window_usable(hwnd) -> bool:
    """Yakalanabilir durumda mi?

    Pencere "yasiyor" olsa da GIZLENMIS olabilir (kapanan Qt pencereleri bir
    sure HWND'yi korur, oyun kendini gizleyebilir). Gizli pencerenin cizim
    yuzeyi yoktur; bu durumda hedefi kaybetmis sayip yeniden aramak gerekir,
    aksi halde olu bir HWND'ye kilitlenip kalirdik.
    """
    return (is_window_alive(hwnd) and is_window_visible(hwnd)
            and not is_cloaked(hwnd))


def is_window_minimized(hwnd) -> bool:
    if not WINAPI_AVAILABLE or not hwnd:
        return False
    try:
        return bool(user32.IsIconic(hwnd))
    except Exception:
        return False


def restore_no_activate(hwnd) -> bool:
    """Simge durumundaki pencereyi ODAK CALMADAN geri getirir.

    Arka plan modunun amaci gozetimsiz calismak; SW_SHOWNOACTIVATE pencereyi
    kullanicinin yaptigi isin ARKASINDA geri acar.
    """
    if not WINAPI_AVAILABLE or not hwnd:
        return False
    try:
        return bool(user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE))
    except Exception:
        return False


def is_cloaked(hwnd) -> bool:
    """DWM tarafindan gizlenmis pencere (baska sanal masaustu, UWP kabugu)."""
    if dwmapi is None or not hwnd:
        return False
    try:
        value = wintypes.DWORD(0)
        result = dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), wintypes.DWORD(DWMWA_CLOAKED),
            ctypes.byref(value), ctypes.sizeof(value),
        )
        return result == 0 and value.value != 0
    except Exception:
        return False


def window_bounds(hwnd):
    """(x, y, w, h) - PENCERE dikdortgeni (fiziksel px). PrintWindow uzayi."""
    if not WINAPI_AVAILABLE or not hwnd:
        return None
    try:
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width <= 0 or height <= 0:
            return None
        return (rect.left, rect.top, width, height)
    except Exception:
        return None


def window_client_bounds(hwnd):
    """(x, y, w, h) - CLIENT alani, ekran koordinatinda (fiziksel px).

    Yakalanan karenin origin'i budur; ScreenScanner.region() ekran
    dikdortgeninden bu origin'i cikararak dogru dilimi alir.
    """
    if not WINAPI_AVAILABLE or not hwnd:
        return None
    try:
        rect = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width <= 0 or height <= 0:
            return None
        point = wintypes.POINT(0, 0)
        if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
            return None
        return (int(point.x), int(point.y), int(width), int(height))
    except Exception:
        return None


def window_metrics(hwnd):
    """Pencerenin HEM ekran HEM kendi cizim uzayindaki olculeri.

    DPI tuzagi: ekran olcekleme aciksa (orn. %125) ve hedef uygulama DPI
    farkindasi DEGILSE, Windows onu kendi kucuk cozunurlugunde cizdirip ekrana
    buyulterek basar. Biz PER_MONITOR_AWARE oldugumuz icin GetClientRect bize
    BUYUTULMUS (fiziksel) olcuyu verir; oysa pencerenin DC'si kendi KUCUK
    olcusundedir. Olculer karistirilirsa yakalanan karenin sag/alt tarafi siyah
    kalir (gercek olcum: oyun 1366x768 cizerken client 1707x960 gorunuyordu).

    Bu yuzden cizim kendi olcusunde yapilir, sonra kare fiziksel client
    olcusune buyutulur; boylece ekran koordinatli kalibrasyon dikdortgenleri
    HIC DEGISMEDEN calismaya devam eder.
    """
    client = window_client_bounds(hwnd)
    if client is None:
        return None
    cx, cy, cw, ch = client
    metrics = {
        "client": client,                  # fiziksel/ekran uzayi
        "render_client": (cw, ch),         # pencerenin kendi uzayi
        "render_window": None,
        "client_offset": (0, 0),
        "scaled": False,
    }
    rect = window_bounds(hwnd)
    if rect is not None:
        metrics["render_window"] = (rect[2], rect[3])
        metrics["client_offset"] = (cx - rect[0], cy - rect[1])

    scale = render_scale(hwnd)
    if scale == 1.0:
        return metrics

    def scaled(value):
        return max(1, int(round(value * scale)))

    metrics["render_client"] = (scaled(cw), scaled(ch))
    metrics["scaled"] = True
    if rect is not None:
        metrics["render_window"] = (scaled(rect[2]), scaled(rect[3]))
        metrics["client_offset"] = (int(round((cx - rect[0]) * scale)),
                                    int(round((cy - rect[1]) * scale)))
    return metrics


def render_scale(hwnd) -> float:
    """Pencerenin KENDI cizim uzayi / fiziksel piksel orani.

    Ekran olcekleme aciksa (orn. %125) ve pencere DPI farkindasi DEGILSE,
    GetDpiForWindow 96 doner ama monitorun etkin DPI'si 120'dir: pencere
    1366x768 cizer, Windows onu ekranda 1707x960'a buyutur. Oran 96/120 = 0.8.
    DPI farkindasi pencerelerde iki deger de ayni oldugu icin oran 1.0 cikar ve
    hicbir sey degismez.
    """
    if not WINAPI_AVAILABLE or not hwnd:
        return 1.0
    try:
        window_dpi = int(user32.GetDpiForWindow(hwnd))
    except Exception:
        return 1.0
    if window_dpi <= 0:
        return 1.0
    monitor_dpi = _monitor_dpi(hwnd)
    if monitor_dpi <= 0 or monitor_dpi == window_dpi:
        return 1.0
    return float(window_dpi) / float(monitor_dpi)


def _monitor_dpi(hwnd) -> int:
    try:
        shcore = ctypes.WinDLL("shcore")
    except Exception:
        return 0
    try:
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = wintypes.HANDLE
        monitor = user32.MonitorFromWindow(hwnd, 2)     # MONITOR_DEFAULTTONEAREST
        if not monitor:
            return 0
        dpi_x = wintypes.UINT()
        dpi_y = wintypes.UINT()
        if shcore.GetDpiForMonitor(monitor, 0,          # MDT_EFFECTIVE_DPI
                                   ctypes.byref(dpi_x),
                                   ctypes.byref(dpi_y)) != 0:
            return 0
        return int(dpi_x.value)
    except Exception:
        return 0


def _resize_nearest(frame, width, height):
    """En yakin komsu buyutme: duz renkli barlarin RENGI hic bozulmaz."""
    if frame.shape[1] == width and frame.shape[0] == height:
        return frame
    try:
        import cv2

        return cv2.resize(frame, (width, height), interpolation=cv2.INTER_NEAREST)
    except Exception:
        rows = (np.arange(height) * frame.shape[0] // height).clip(0, frame.shape[0] - 1)
        cols = (np.arange(width) * frame.shape[1] // width).clip(0, frame.shape[1] - 1)
        return np.ascontiguousarray(frame[rows][:, cols])


def screen_to_client(hwnd, x, y):
    """Ekran pikseli -> client pikseli. PostMessage fare mesajlari icin."""
    bounds = window_client_bounds(hwnd)
    if bounds is None:
        return None
    cx, cy, cw, ch = bounds
    lx, ly = int(x) - cx, int(y) - cy
    if lx < 0 or ly < 0 or lx >= cw or ly >= ch:
        return None
    return (lx, ly)


# ---------------------------------------------------------------- pencere arama
def list_windows(title_substring: str = "", own_pid: int = None):
    """Gorunur, cloaked olmayan ust duzey pencereler (bizimkiler haric).

    Donen sozlukler: hwnd, title, cls, pid, rect, client.
    """
    if not WINAPI_AVAILABLE:
        return []
    own_pid = os.getpid() if own_pid is None else own_pid
    needle = (title_substring or "").strip().casefold()
    found = []

    def callback(hwnd, _lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            title = window_title(hwnd)
            if not title:
                return True
            if needle and needle not in title.casefold():
                return True
            pid = window_pid(hwnd)
            if pid == own_pid:
                return True
            if is_cloaked(hwnd):
                return True
            client = window_client_bounds(hwnd)
            minimized = is_window_minimized(hwnd)
            if client is None and not minimized:
                return True
            # Simge durumundaki pencerenin client alani 0x0'dir; yine de ADAY
            # sayilir, aksi halde oyun kucultulmusken hic bulunamaz ve
            # WindowGuard onu geri getiremezdi.
            found.append({
                "hwnd": int(hwnd),
                "title": title,
                "cls": window_class(hwnd),
                "pid": pid,
                "rect": window_bounds(hwnd),
                "client": client,
                "minimized": minimized,
            })
        except Exception:
            pass
        return True

    try:
        user32.EnumWindows(WNDENUMPROC(callback), 0)
    except Exception:
        return []
    return found


def find_game_window(title_substring: str, own_pid: int = None):
    """Basligi eslesen en olasi pencereyi bulur.

    Siralama: tam eslesme > basla-eslesme > icerme; esitlikte en buyuk client
    alani. Kendi surecimiz DISLANIR; aksi halde kendi canli gorunum penceremiz
    hedef sanilirdi.
    """
    needle = (title_substring or "").strip()
    if not needle:
        return None
    candidates = list_windows(needle, own_pid)
    if not candidates:
        return None
    low = needle.casefold()

    def score(item):
        title = item["title"].casefold()
        if title == low:
            rank = 3
        elif title.startswith(low):
            rank = 2
        else:
            rank = 1
        client = item.get("client")
        area = client[2] * client[3] if client else 0
        # Ayakta duran pencere, simge durumundakine yeglenir (ayni baslikta
        # iki kopya varsa calisani secilsin).
        return (rank, 0 if item.get("minimized") else 1, area)

    return max(candidates, key=score)["hwnd"]


# ---------------------------------------------------------------- yakalayici
class WindowGrabber:
    """Tek HWND'den kare uretir. YALNIZ olusturuldugu thread'te kullanilir.

    grab() -> (BGR ndarray | None, (origin_x, origin_y))
    Donen kare her zaman CLIENT alanidir; origin de client'in ekran kosesidir.
    """

    def __init__(self, hwnd_provider, mode: str = GRAB_AUTO):
        self._provider = hwnd_provider
        self._mode = mode if mode in GRAB_MODES or mode == GRAB_AUTO else GRAB_AUTO
        self._active = None if self._mode == GRAB_AUTO else self._mode
        self._src_dc = None
        self._client_dc = None
        self._dc_hwnd = None
        self._mem_dc = None
        self._bitmap = None
        self._old_bitmap = None
        self._bitmap_size = (0, 0)
        self._buffer = None
        self._info = None
        self.last_error = ""

    # -------------------------------------------------------------- yasam
    def close(self):
        self._release()

    def active_mode(self):
        return self._active

    def _free_bitmap(self):
        try:
            if self._mem_dc and self._old_bitmap:
                gdi32.SelectObject(self._mem_dc, self._old_bitmap)
            if self._bitmap:
                gdi32.DeleteObject(self._bitmap)
        except Exception:
            pass
        self._bitmap = None
        self._old_bitmap = None
        self._bitmap_size = (0, 0)
        self._buffer = None
        self._info = None

    def _release(self):
        self._free_bitmap()
        try:
            if self._mem_dc:
                gdi32.DeleteDC(self._mem_dc)
        except Exception:
            pass
        try:
            if self._src_dc and self._dc_hwnd:
                user32.ReleaseDC(self._dc_hwnd, self._src_dc)
        except Exception:
            pass
        try:
            if self._client_dc and self._dc_hwnd:
                user32.ReleaseDC(self._dc_hwnd, self._client_dc)
        except Exception:
            pass
        self._mem_dc = None
        self._src_dc = None
        self._client_dc = None
        self._dc_hwnd = None

    # -------------------------------------------------------------- yakalama
    def grab(self):
        if not WINAPI_AVAILABLE:
            self.last_error = "Windows API kullanilamiyor"
            return None, (0, 0)

        hwnd = self._provider() if callable(self._provider) else self._provider
        if not hwnd or not is_window_usable(hwnd):
            self._release()
            self.last_error = "pencere yok"
            return None, (0, 0)
        if is_window_minimized(hwnd):
            self.last_error = "pencere simge durumunda"
            return None, (0, 0)

        metrics = window_metrics(hwnd)
        if metrics is None:
            self.last_error = "pencere olcusu alinamadi"
            return None, (0, 0)
        origin = (metrics["client"][0], metrics["client"][1])

        for mode in self._candidates():
            frame = self._grab_once(hwnd, metrics, mode)
            if frame is not None:
                self._active = mode
                self.last_error = ""
                return frame, origin
        if self._mode == GRAB_AUTO:
            self._active = None          # sonraki karede varyantlari yeniden dene
        return None, origin

    def _candidates(self):
        if self._mode != GRAB_AUTO:
            return (self._mode,)
        if self._active:
            others = tuple(m for m in GRAB_ORDER if m != self._active)
            return (self._active,) + others
        return GRAB_ORDER

    def _grab_once(self, hwnd, metrics, mode):
        _cx, _cy, target_w, target_h = metrics["client"]
        render_w, render_h = metrics["render_client"]
        crop = None
        if mode in _CLIENT_MODES:
            width, height = render_w, render_h
        else:
            window_size = metrics["render_window"]
            if not window_size:
                self.last_error = "pencere dikdortgeni yok"
                return None
            width, height = window_size
            offset_x, offset_y = metrics["client_offset"]
            crop = (offset_x, offset_y, render_w, render_h)
        if width <= 0 or height <= 0:
            return None
        if not self._ensure_surface(hwnd, width, height):
            return None

        try:
            gdi32.SelectObject(self._mem_dc, self._bitmap)
            if mode == GRAB_BITBLT:
                # BitBlt kaynagi CLIENT DC'sidir (GetDC), pencere DC'si degil:
                # boylece kenarlik/baslik cubugu disarida kalir ve origin
                # client kosesiyle birebir ortusur.
                ok = bool(gdi32.BitBlt(
                    self._mem_dc, 0, 0, width, height, self._client_dc, 0, 0, SRCCOPY
                ))
            else:
                flags = 0
                if mode in (GRAB_CLIENT, GRAB_WINDOW):
                    flags |= PW_RENDERFULLCONTENT
                if mode in (GRAB_CLIENT, GRAB_CLIENT0):
                    flags |= PW_CLIENTONLY
                ok = bool(user32.PrintWindow(hwnd, self._mem_dc, flags))
            # GetDIBits, bitmap bir DC'ye SECILIYKEN cagrilmamali (MSDN).
            gdi32.SelectObject(self._mem_dc, self._old_bitmap)
        except Exception as exc:
            self.last_error = "cizim hatasi: {}".format(exc)
            return None

        if not ok:
            self.last_error = "{}: PrintWindow/BitBlt basarisiz".format(mode)
            return None

        raw = self._read_bitmap(width, height)
        if raw is None:
            self.last_error = "{}: piksel okunamadi".format(mode)
            return None

        if crop is not None:
            x, y, w, h = crop
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(width, x + w), min(height, y + h)
            if x1 <= x0 or y1 <= y0:
                self.last_error = "{}: client kirpmasi bos".format(mode)
                return None
            raw = raw[y0:y1, x0:x1]

        frame = np.ascontiguousarray(raw[:, :, :3])
        # Siyah kare = yakalanamadi (exclusive fullscreen / surucu). Vision'a
        # siyah besleme; bayat kare gatinge dussun.
        if not frame[::8, ::8].any():
            self.last_error = "{}: kare siyah".format(mode)
            return None
        # Pencere kendi olcusunde ciziyorsa ekran (fiziksel) olcusune buyut:
        # kalibrasyon dikdortgenleri ekran uzayindadir, degismeden calissin.
        return _resize_nearest(frame, target_w, target_h)

    def _ensure_surface(self, hwnd, width, height):
        if self._dc_hwnd != hwnd or self._src_dc is None:
            self._release()
            src = user32.GetWindowDC(hwnd)
            if not src:
                self.last_error = "pencere DC alinamadi"
                return False
            self._src_dc = src
            self._dc_hwnd = hwnd
            self._client_dc = user32.GetDC(hwnd)     # BitBlt icin client DC'si
            self._mem_dc = gdi32.CreateCompatibleDC(src)
            if not self._mem_dc:
                self.last_error = "bellek DC olusturulamadi"
                self._release()
                return False

        if self._bitmap_size != (width, height) or self._bitmap is None:
            self._free_bitmap()
            bitmap = gdi32.CreateCompatibleBitmap(self._src_dc, width, height)
            if not bitmap:
                self.last_error = "bitmap olusturulamadi"
                return False
            self._old_bitmap = gdi32.SelectObject(self._mem_dc, bitmap)
            gdi32.SelectObject(self._mem_dc, self._old_bitmap)
            self._bitmap = bitmap
            self._bitmap_size = (width, height)
            self._buffer = ctypes.create_string_buffer(width * height * 4)
            info = BITMAPINFO()
            info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            info.bmiHeader.biWidth = width
            info.bmiHeader.biHeight = -height        # negatif = ust-alt siralama
            info.bmiHeader.biPlanes = 1
            info.bmiHeader.biBitCount = 32
            info.bmiHeader.biCompression = BI_RGB
            self._info = info
        return True

    def _read_bitmap(self, width, height):
        try:
            lines = gdi32.GetDIBits(
                self._src_dc, self._bitmap, 0, height,
                ctypes.cast(self._buffer, ctypes.c_void_p),
                ctypes.byref(self._info), DIB_RGB_COLORS,
            )
        except Exception:
            return None
        if lines != height:
            return None
        array = np.frombuffer(self._buffer, dtype=np.uint8, count=width * height * 4)
        return array.reshape(height, width, 4)      # BGRA


# ------------------------------------------------------- arka plan girdi (mesaj)
# Interception/SetCursorPos donanim seviyesindedir: nereye odaklanilmissa oraya
# gider. Arka plan modunda tus/tik DOGRUDAN hedef pencerenin mesaj kuyruguna
# birakilir; boylece oyun arkada dururken kullanicinin isine karisilmaz.
# PostMessage asenkron ve thread-safe'tir: modul thread'lerinden guvenle
# cagrilir, GUI thread'ine gecis gerekmez.
def vk_from_scan(scan: int) -> int:
    """Tarama kodu -> sanal tus kodu. KEYCODES tek kaynak kalsin diye."""
    if not WINAPI_AVAILABLE:
        return 0
    try:
        return int(user32.MapVirtualKeyW(int(scan), MAPVK_VSC_TO_VK_EX))
    except Exception:
        return 0


def scan_from_vk(vk: int) -> int:
    if not WINAPI_AVAILABLE:
        return 0
    try:
        return int(user32.MapVirtualKeyW(int(vk), MAPVK_VK_TO_VSC))
    except Exception:
        return 0


def _key_lparam(scan: int, extended: bool, released: bool) -> int:
    lparam = 1 | ((int(scan) & 0xFF) << 16)
    if extended:
        lparam |= (KF_EXTENDED << 16)
    if released:
        lparam |= (1 << 30) | (1 << 31)      # onceki durum basili + birakildi
    return lparam


def post_key_down(hwnd, vk: int, scan: int, extended: bool = False) -> bool:
    if not WINAPI_AVAILABLE or not hwnd:
        return False
    try:
        return bool(user32.PostMessageW(
            hwnd, WM_KEYDOWN, int(vk), _key_lparam(scan, extended, False)
        ))
    except Exception:
        return False


def post_key_up(hwnd, vk: int, scan: int, extended: bool = False) -> bool:
    if not WINAPI_AVAILABLE or not hwnd:
        return False
    try:
        return bool(user32.PostMessageW(
            hwnd, WM_KEYUP, int(vk), _key_lparam(scan, extended, True)
        ))
    except Exception:
        return False


def _mouse_lparam(cx: int, cy: int) -> int:
    return ((int(cy) & 0xFFFF) << 16) | (int(cx) & 0xFFFF)


def post_mouse(hwnd, message: int, wparam: int, cx: int, cy: int) -> bool:
    """Client koordinatli fare mesaji."""
    if not WINAPI_AVAILABLE or not hwnd:
        return False
    try:
        return bool(user32.PostMessageW(
            hwnd, int(message), int(wparam), _mouse_lparam(cx, cy)
        ))
    except Exception:
        return False


def foreground_window():
    if not WINAPI_AVAILABLE:
        return None
    try:
        return int(user32.GetForegroundWindow() or 0) or None
    except Exception:
        return None


def is_process_elevated(pid=None) -> bool:
    """Surec yonetici haklariyla mi calisiyor?

    Oyun yukseltilmisse, yukseltilmemis bir surec ona ne mesaj gonderebilir
    (UIPI) ne de odagini degistirebilir. Kullaniciya dogru uyariyi vermek icin.

    Tuzak: HANDLE donduren/alan cagrilarda argtypes-restype AYARLANMAZSA
    64-bit'te handle kirpilir; GetCurrentProcess'in sahte handle'i (-1) bozulur
    ve fonksiyon sessizce YANLIS sonuc verir.
    """
    if not WINAPI_AVAILABLE:
        return False
    try:
        handle = (_kernel32.GetCurrentProcess() if pid is None
                  else _kernel32.OpenProcess(0x1000, False, int(pid)))
        if not handle:
            return False
        try:
            token = wintypes.HANDLE()
            if not _advapi32.OpenProcessToken(handle, 0x0008, ctypes.byref(token)):
                return False
            try:
                value = wintypes.DWORD()
                size = wintypes.DWORD()
                if not _advapi32.GetTokenInformation(
                        token, 20, ctypes.byref(value),      # TokenElevation
                        ctypes.sizeof(value), ctypes.byref(size)):
                    return False
                return bool(value.value)
            finally:
                _kernel32.CloseHandle(token)
        finally:
            if pid is not None:
                _kernel32.CloseHandle(handle)
    except Exception:
        return False


def set_foreground(hwnd, timeout: float = 0.35) -> bool:
    """Pencereyi on plana alir.

    SetForegroundWindow, cagiran surec on planda degilse Windows tarafindan
    reddedilir (yalnizca gorev cubugunu yanip sondurur). Standart cozum:
    cagiran thread'i o anki on plan thread'ine gecici olarak baglamak.
    """
    if not WINAPI_AVAILABLE or not hwnd:
        return False
    try:
        if int(user32.GetForegroundWindow() or 0) == int(hwnd):
            return True
    except Exception:
        return False

    current = foreground_window()
    own_thread = _kernel32.GetCurrentThreadId()
    other_thread = 0
    if current:
        try:
            other_thread = int(user32.GetWindowThreadProcessId(current, None))
        except Exception:
            other_thread = 0
    attached = False
    try:
        if other_thread and other_thread != own_thread:
            attached = bool(user32.AttachThreadInput(own_thread, other_thread, True))
        try:
            user32.AllowSetForegroundWindow(-1)          # ASFW_ANY
        except Exception:
            pass
        if is_window_minimized(hwnd):
            restore_no_activate(hwnd)
        # ALT dokunusu on plan kilidini acar: attach tek basina yetmedigi
        # olculdu (odak oyundayken kullaniciya geri verilemiyordu).
        try:
            user32.keybd_event(0x12, 0, 0, 0)
            user32.keybd_event(0x12, 0, 2, 0)
        except Exception:
            pass
        user32.SetForegroundWindow(hwnd)
        try:
            user32.BringWindowToTop(hwnd)
        except Exception:
            pass
    except Exception:
        return False
    finally:
        if attached:
            try:
                user32.AttachThreadInput(own_thread, other_thread, False)
            except Exception:
                pass

    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        if foreground_window() == int(hwnd):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.01)


class BackgroundFocus:
    """Oyuna ONE CIKARMADAN klavye odagi verir ve odagi KORUR.

    Neden boyle: olculdu ki bu istemci girdiyi yalnizca ODAKTAYKEN isliyor
    (pencere mesajlari etkisiz, cekirdek seviyesi Interception bile odaksiz
    gecmiyor - oyun DirectInput kullaniyor). Yakalama arka planda calistigi
    icin pencerenin GORUNUR olmasi gerekmiyor; yalnizca ODAK gerekiyor.

    Iki tuzak vardir ve ikisi de olculerek cozuldu:

    1) `SetForegroundWindow` pencereyi GORSEL olarak da one firlatir. Atak
       modulu 50 ms'de bir tus gonderdiginden bu, oyunun surekli one ziplamasi
       demekti. Cozum: on plan cagrisi HIC kullanilmaz; oyunun thread'i on
       plandaki pencerenin girdi kuyruguna baglanip (`AttachThreadInput`) odak
       `SetFocus` ile verilir; hemen ardindan KULLANICININ aktif penceresi
       `SWP_NOACTIVATE` ile uste cekilir (`keep_on_top`). Oyunu z-sirasinda
       ZORLA en alta itMEYIZ (kullanici istegi): hangi pencere neredeyse orada
       kalir, yalniz kullanicinin penceresi gorunur olur, oyun ise odaga sahip.

    2) Odagi HER TUSTA alip geri vermek hem pahali hem sarsintiliydi. Odak bir
       kez alinir ve korunur; `ensure()` yalnizca odak kaybedilmisse yeniden
       alir (normalde tek karsilastirma, sifir ek yuk).

    Kullanici OYUNA gecerse (`foreground == oyun`) `ensure()` hicbir seye
    dokunmaz: normal mod gibi dogrudan gonderilir. Kullanici baska pencereye
    gecerse arka plan davranisi kendiliginden devreye girer. `release()` odagi
    kullanicinin penceresine geri verir (master kapaninca).
    """

    def __init__(self):
        self._user_window = None
        self.last_error = ""

    def user_window(self):
        return self._user_window

    def ensure(self, hwnd) -> bool:
        """Odak oyunda degilse ONE CIKARMADAN alir. Zaten odaktaysa hicbir sey yapmaz."""
        if not WINAPI_AVAILABLE or not hwnd:
            self.last_error = "pencere yok"
            return False
        if not is_window_alive(hwnd):
            self.last_error = "pencere kapandi"
            return False
        current = foreground_window()
        if current == int(hwnd):
            # Kullanici oyuna gecti: NORMAL mod gibi davran, hicbir pencereye
            # dokunma. Geri verilecek bir pencere de yok (kullanici zaten oyunda).
            self._user_window = None
            return True                       # hizli yol: zaten odakta
        if current and current != int(hwnd):
            self._user_window = current       # ustte tutacagimiz pencere
        return self._take_focus(int(hwnd))

    def _take_focus(self, hwnd) -> bool:
        front = foreground_window()
        front_thread = 0
        if front:
            try:
                front_thread = int(user32.GetWindowThreadProcessId(front, None))
            except Exception:
                front_thread = 0
        try:
            game_thread = int(user32.GetWindowThreadProcessId(hwnd, None))
        except Exception:
            self.last_error = "oyun thread'i alinamadi"
            return False
        own_thread = _kernel32.GetCurrentThreadId()

        attached = []
        try:
            for thread in (front_thread, own_thread):
                if thread and thread != game_thread:
                    if user32.AttachThreadInput(thread, game_thread, True):
                        attached.append(thread)
            user32.SetFocus(hwnd)
            # Odak alinirken Windows oyunu z-sirasinin tepesine tasima
            # egilimindedir; kullanici o anda ne yapiyorsa onun onune ziplar.
            # Oyunu ZORLA en alta itMIYORUZ (kullanici sikayeti): z-sirasini
            # oldugu gibi birakip yalniz KULLANICININ aktif penceresini uste
            # sabitliyoruz. SWP_NOACTIVATE odaga DOKUNMAZ; oyun odaga sahip
            # olmaya devam eder ama kullanici kendi penceresini gormeye devam
            # eder. Thread'ler ayrilmadan once yapilir: bosluk ne kadar kisaysa
            # ekranda o kadar kisa bir parlama olur.
            self._restore_user_top()
        except Exception as exc:
            self.last_error = "odak verilemedi: {}".format(exc)
            return False
        finally:
            for thread in attached:
                try:
                    user32.AttachThreadInput(thread, game_thread, False)
                except Exception:
                    pass

        self._restore_user_top()    # ayrilma sirasinda oyun yeniden yukseldiyse

        ok = foreground_window() == hwnd
        if not ok:
            self.last_error = "odak oyuna gecmedi"
        return ok

    def _restore_user_top(self):
        """Kullanicinin aktif penceresini z-sirasinda uste sabitler (odaksiz).

        Oyun odagi alirken gorsel olarak one ziplarsa, kullanicinin o an
        kullandigi pencere altta kalmasin diye onu geri uste ceker. Oyunun
        z-pozisyonuna DOKUNMAZ: hangi pencere neredeyse orada kalir, yalniz
        kullanicinin penceresi gorunur olur.
        """
        target = self._user_window
        if target and is_window_alive(target):
            keep_on_top(target)

    def release(self) -> bool:
        """Odagi kullanicinin penceresine geri verir (master kapanisi)."""
        target = self._user_window
        self._user_window = None
        if not target or not is_window_alive(target):
            return False
        if foreground_window() == int(target):
            return True
        return set_foreground(target, timeout=0.3)


def send_to_back(hwnd) -> bool:
    """Pencereyi z-sirasinda EN ALTA iter ama ODAGI BIRAKMAZ (SWP_NOACTIVATE).

    Arka plan modunun gorsel omurgasi: oyun odaga sahip olmaya devam eder
    (DirectInput bunu sart kosuyor) ama kullanicinin onune ziplamaz.
    """
    if not WINAPI_AVAILABLE or not hwnd or not is_window_alive(hwnd):
        return False
    try:
        return bool(user32.SetWindowPos(
            hwnd, HWND_BOTTOM, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        ))
    except Exception:
        return False


def keep_on_top(hwnd) -> bool:
    """Pencereyi z-sirasinda uste alir ama ODAK VERMEZ (SWP_NOACTIVATE).

    Oyun odagi aldiginda kullanicinin penceresi gorsel olarak altta kalmasin
    diye kullanilir; kullanicinin gordugu sey degismez.
    """
    if not WINAPI_AVAILABLE or not hwnd or not is_window_alive(hwnd):
        return False
    try:
        return bool(user32.SetWindowPos(
            hwnd, HWND_TOP, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        ))
    except Exception:
        return False


def child_at_client_point(hwnd, cx: int, cy: int):
    """Verilen client noktasindaki gercek alt pencere (yoksa hwnd'nin kendisi).

    Bazi istemciler tiklari yalnizca cizim alt penceresinde isler; gerekirse
    mesaj hedefi buraya cevrilir.
    """
    if not WINAPI_AVAILABLE or not hwnd:
        return hwnd
    try:
        child = user32.RealChildWindowFromPoint(hwnd, wintypes.POINT(int(cx), int(cy)))
        return int(child) if child else hwnd
    except Exception:
        return hwnd
