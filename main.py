"""Birleşik Knight Online yardımcı programı - giriş noktası.

Sıra önemlidir: DPI farkındalığı QApplication'dan ÖNCE ayarlanır (tuzak #2),
sonra tek kopya kilidi, sonra servisler ve pencere.
"""

import os
import sys


def _set_dpi_awareness():
    """Qt geometrisi, mss pikselleri ve SetCursorPos aynı fiziksel uzayda olsun."""
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PER_MONITOR_AWARE
            return "per-monitor"
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
            return "system"
    except Exception:
        return "yok"


DPI_MODE = _set_dpi_awareness()


def _base_dir() -> str:
    """Ayarların yazılacağı klasör.

    PyInstaller onefile'da __file__ geçici açılım klasörünü gösterir; oraya
    yazılan profiles.ini çıkışta silinir. Donmuş halde exe'nin yanı kullanılır.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication, QMessageBox        # noqa: E402

from app.app_state import AppState                            # noqa: E402
from app.calibration.calibration_manager import CalibrationManager  # noqa: E402
from app.config.settings_manager import SettingsManager       # noqa: E402
from app.constants import APP_NAME, SINGLE_INSTANCE_MUTEX     # noqa: E402
from app.core.death_guard import DeathGuard                   # noqa: E402
from app.core.module_base import ModuleContext                # noqa: E402
from app.core.module_manager import ModuleManager             # noqa: E402
from app.core.party_tracker import PartyTracker               # noqa: E402
from app.core.status_reader import StatusReader               # noqa: E402
from app.live_status import LiveStatus                        # noqa: E402
from app.modules.attack_module import AttackModule            # noqa: E402
from app.modules.buff_module import BuffModule                # noqa: E402
from app.modules.clicker_module import ClickRecorder, ClickerModule  # noqa: E402
from app.modules.heal_module import HealModule                # noqa: E402
from app.modules.pot_module import PotModule                  # noqa: E402
from app.services.hotkey_service import HotkeyService         # noqa: E402
from app.services.input_service import InputService           # noqa: E402
from app.services.screen_scanner import ScreenScanner         # noqa: E402
from app.services.sound_service import SoundService           # noqa: E402
from app.services.window_guard import WindowGuard             # noqa: E402
from app.ui.main_window import MainWindow                     # noqa: E402


def _acquire_single_instance():
    """İkinci kopyayı engelle. Kilit alınamazsa (None, mesaj) döner."""
    try:
        import win32api
        import win32event
        import winerror

        handle = win32event.CreateMutex(None, False, SINGLE_INSTANCE_MUTEX)
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            return None, "Program zaten çalışıyor."
        return handle, ""
    except Exception:
        return True, ""          # kilit kurulamadı: engelleme yapma


def build_services(settings_path):
    state = AppState()
    live = LiveStatus()
    sound = SoundService(enabled=True)
    input_service = InputService(state)
    scanner = ScreenScanner(live_status=live)
    calibration = CalibrationManager()
    ctx = ModuleContext(state, input_service, scanner, calibration, live, sound)

    party = PartyTracker(scanner, calibration)
    manager = ModuleManager(ctx)
    manager.register(PotModule(ctx))
    manager.register(AttackModule(ctx))
    manager.register(HealModule(ctx, party))
    manager.register(BuffModule(ctx))
    manager.register(ClickerModule(ctx))

    settings = SettingsManager(settings_path)
    settings.load()

    return {
        "ctx": ctx,
        "manager": manager,
        "settings": settings,
        "party": party,
        "hotkeys": HotkeyService(),
        "window_guard": WindowGuard(state, scanner=scanner),
        "death_guard": DeathGuard(ctx),
        "status_reader": StatusReader(ctx, party),
        "recorder": ClickRecorder(),
    }


def _apply_native_light_theme(app):
    """Açık klasik tema — qdarkstyle YOK (anket kararı).

    Stil ve palet açıkça kuruluyor ki Windows koyu moddayken bile panel açık
    kalsın ve görünüm makineden makineye değişmesin. Üzerine minimal QSS
    (app/ui/theme.py) gelir: belirgin seçili sekme + sıkı boşluklar.
    """
    from PyQt5.QtWidgets import QStyleFactory

    from app.ui.theme import apply_theme

    chosen = ""
    # QSS ile en tutarlı çizen stil Fusion'dır; bulunamazsa native'e düşülür.
    for name in ("Fusion", "windowsvista", "Windows"):
        style = QStyleFactory.create(name)
        if style is not None:
            app.setStyle(style)
            app.setPalette(style.standardPalette())
            chosen = name
            break
    apply_theme(app)
    return chosen


def main():
    handle, message = _acquire_single_instance()
    if handle is None:
        app = QApplication(sys.argv)
        QMessageBox.warning(None, APP_NAME, message)
        return 1

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)     # tepsiye küçültünce kapanmasın
    _apply_native_light_theme(app)

    from app.ui.input_guard import install_input_guards
    install_input_guards(app)                # yanlışlıkla tekerlekle ayar bozma

    services = build_services(os.path.join(_base_dir(), "profiles.ini"))

    window = MainWindow(services)
    window.load_settings()
    window.show()

    services["ctx"].scanner.start()
    services["hotkeys"].start()
    services["window_guard"].start()
    services["status_reader"].start()
    services["death_guard"].start()
    services["manager"].start_all()

    input_service = services["ctx"].input
    if not input_service.using_interception:
        QMessageBox.information(
            window, "Girdi arka ucu",
            "Interception sürücüsü kullanılamıyor, PyAutoGUI/win32 yedeğine "
            "geçildi.\n\nSebep: {}\n\nProgram çalışır; arka uç Bilgi sekmesinde "
            "gösterilir.".format(input_service.driver_error or "bilinmiyor"),
        )

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
