"""Her modülün üst şeridi: aktif/pasif anahtarı + kısayol + döngü hızı.

Anahtar bir TİK değil, master düğmesinin solgun kardeşi olan bir düğmedir:
master tek dolu renk alan olduğu için hiyerarşi bakışta anlaşılır.
"""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from ..theme import ROW_SPACING
from .card import Card
from .common import HotkeyButton, StatusDot


class ModuleToggle(QPushButton):
    """AKTİF / PASİF anahtarı. QCheckBox API'siyle uyumlu kalır."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedWidth(74)
        self.setToolTip(
            "Modülü aç/kapa. Master kapalıyken bu tik hatırlanır ama modül "
            "çalışmaz."
        )
        self.toggled.connect(self._refresh)
        self._error = False
        self._refresh(False)

    def set_error(self, value):
        self._error = bool(value)
        self._refresh(self.isChecked())

    def _refresh(self, checked):
        if self._error:
            self.setObjectName("moduleError")
            self.setText("HATA")
        else:
            self.setObjectName("moduleOn" if checked else "moduleOff")
            self.setText("AKTİF" if checked else "PASİF")
        self.style().unpolish(self)
        self.style().polish(self)


class ModuleHeader(Card):
    enabledChanged = pyqtSignal(bool)
    hotkeyChanged = pyqtSignal(str)
    loopChanged = pyqtSignal(int)

    def __init__(self, caption, module_id, hotkey_service, default_loop_ms,
                 parent=None):
        super().__init__(caption, parent)
        self.module_id = module_id

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(ROW_SPACING)

        self.dot = StatusDot(self)
        top.addWidget(self.dot)

        # Adı "check" kalıyor: sekmeler, ana pencere ve testler bu API'yi
        # kullanıyor (setChecked / isChecked / toggled).
        self.check = ModuleToggle(self)
        top.addWidget(self.check)

        self.hotkey = HotkeyButton(
            "Kısayol", hotkey_service, "module::{}".format(module_id), self
        )
        top.addWidget(self.hotkey, 1)
        self.add_layout(top)

        # Döngü hızı artık sabittir (DEFAULT_LOOP_MS): kullanıcı ayarı kaldırıldı,
        # yerini kalibrasyon/hız ayarı aldı. Değer yalnızca içeride tutulur;
        # eski profillerdeki loop_ms kaydı yüklenmeye devam eder.
        self._loop_ms = int(default_loop_ms)

        self.check.toggled.connect(self.enabledChanged)
        self.hotkey.keyChanged.connect(self.hotkeyChanged)

    # ------------------------------------------------------------------ veri
    def set_checked_silently(self, value):
        self.check.blockSignals(True)
        self.check.setChecked(bool(value))
        self.check.blockSignals(False)

    def is_checked(self) -> bool:
        return self.check.isChecked()

    def hotkey_value(self) -> str:
        return self.hotkey.key()

    def set_hotkey(self, value):
        self.hotkey.set_key(value)

    def loop_ms(self) -> int:
        return self._loop_ms

    def set_loop_ms(self, value):
        try:
            self._loop_ms = int(value)
        except (TypeError, ValueError):
            pass

    def set_state(self, state):
        self.dot.set_state(state)
        self.check.set_error(state == "error")
