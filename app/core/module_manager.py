"""Master / panik yönetimi ve modül on-kosul denetimi.

Modül tikleri master kapatilip acildiginda KORUNUR. Panik her şeyi anında
durdurur ve YALNIZ master kisayoluyla geri açılır.
"""

from PyQt5.QtCore import QObject, pyqtSignal

from ..constants import BEEP_PANIC


class ModuleManager(QObject):
    masterChanged = pyqtSignal(bool)
    panicChanged = pyqtSignal(bool)
    calibrationMissing = pyqtSignal(str, list)     # (modul kimligi, eksik kayitlar)
    moduleStateChanged = pyqtSignal(str, str, str)
    moduleSelfDisabled = pyqtSignal(str, str)

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._modules = {}

    # ------------------------------------------------------------------ kayit
    def register(self, module):
        self._modules[module.module_id] = module
        module.statusChanged.connect(self.moduleStateChanged)
        module.selfDisabled.connect(self._on_self_disabled)

    def get(self, module_id):
        return self._modules.get(module_id)

    def modules(self):
        return dict(self._modules)

    def start_all(self):
        for module in self._modules.values():
            module.start()

    def stop_all(self):
        for module in self._modules.values():
            module.stop()

    # ------------------------------------------------------------------ master
    @property
    def master_on(self) -> bool:
        return self.ctx.state.master_on.is_set()

    def set_master(self, value: bool) -> bool:
        value = bool(value)
        if value:
            if self.ctx.state.panic.is_set():
                self.ctx.state.panic.clear()
                self.panicChanged.emit(False)
            self.ctx.state.master_on.set()
        else:
            self.ctx.state.master_on.clear()
        self.masterChanged.emit(value)
        return value

    def toggle_master(self) -> bool:
        return self.set_master(not self.master_on)

    # ------------------------------------------------------------------ panik
    @property
    def panicking(self) -> bool:
        return self.ctx.state.panic.is_set()

    def panic(self):
        self.ctx.state.panic.set()
        self.ctx.state.master_on.clear()
        self.ctx.sound.beep(BEEP_PANIC)
        self.panicChanged.emit(True)
        self.masterChanged.emit(False)

    # ------------------------------------------------------------------ moduller
    def missing_calibrations(self, module_id):
        module = self._modules.get(module_id)
        if module is None:
            return []
        required = module.required_now() if hasattr(module, "required_now") else list(
            getattr(module, "required_calibrations", ())
        )
        return self.ctx.calibration.missing(required)

    def request_enable(self, module_id, enabled: bool) -> bool:
        """Modülü ac/kapa. Gereken kalibrasyon yoksa acmaz ve uyari yayar."""
        module = self._modules.get(module_id)
        if module is None:
            return False
        if not enabled:
            module.set_enabled(False)
            return False
        missing = self.missing_calibrations(module_id)
        if missing:
            self.calibrationMissing.emit(module_id, missing)
            module.set_enabled(False)
            return False
        module.clear_error()
        module.set_enabled(True)
        return True

    def disable_all_modules(self):
        for module in self._modules.values():
            module.set_enabled(False)

    def enabled_ids(self):
        return [mid for mid, m in self._modules.items() if m.enabled]

    def _on_self_disabled(self, module_id, reason):
        self.moduleSelfDisabled.emit(module_id, reason)
