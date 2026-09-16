"""Genel sekmesi: HP potu, MP potu, Minör ve 3. içecek.

Program ayarları bloğu (profil, oyun penceresi, kısayollar) bu sekmenin ALTINA
eklenir; ana pencere onu `add_footer()` ile buraya taşır.
"""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QVBoxLayout, QWidget

from ...constants import DEFAULT_LOOP_MS, MODULE_POT
from ...modules.pot_module import ROW_HP, ROW_MINOR, ROW_MP
from ..theme import CARD_SPACING
from ..widgets.card import Card, Divider
from ..widgets.module_header import ModuleHeader
from ..widgets.pot_row_widget import PotRowWidget


class GeneralTab(QWidget):
    changed = pyqtSignal()

    def __init__(self, manager, hotkey_service, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.module = manager.get(MODULE_POT)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(CARD_SPACING + 1)

        self.header = ModuleHeader(
            "Genel · pot", MODULE_POT, hotkey_service, DEFAULT_LOOP_MS["pot"], self
        )
        root.addWidget(self.header)

        box = Card("Pot satırları", self)
        box.setToolTip(
            "Satırlar birbirinden bağımsız çalışır; minör ile pot aynı anda "
            "basabilir. Aynı tuşa 1320 ms içinde iki kez basılmaz."
        )
        self.rows = {
            ROW_HP: PotRowWidget(
                "HP potu", "Kendi HP'n eşiğin altına düşünce pot basılır.",
                with_page=True, default_threshold=50, parent=box,
            ),
            ROW_MP: PotRowWidget(
                "MP potu", "Kendi MP'n eşiğin altına düşünce pot basılır.",
                with_page=True, default_threshold=50, parent=box,
            ),
            ROW_MINOR: PotRowWidget(
                "Minör", "Minör için F sayfası yoktur; yalnızca tuş basılır.",
                with_page=False, default_threshold=70, parent=box,
            ),
        }
        for index, row in enumerate(self.rows.values()):
            if index:
                box.add(Divider(box))
            box.add(row)
            row.changed.connect(self._on_changed)
        root.addWidget(box)

        # Ana pencerenin taşıdığı "Program ayarları" bloğu buraya oturur.
        self.footer_slot = QVBoxLayout()
        self.footer_slot.setContentsMargins(0, 0, 0, 0)
        self.footer_slot.setSpacing(CARD_SPACING)
        root.addLayout(self.footer_slot)
        root.addStretch(1)

        self.header.enabledChanged.connect(self._on_toggle)
        self.header.hotkeyChanged.connect(lambda _: self.changed.emit())
        self.header.loopChanged.connect(self._on_loop)

    def add_footer(self, widget):
        self.footer_slot.addWidget(widget)

    # ------------------------------------------------------------------ olaylar
    def _on_changed(self):
        self.apply()
        self.changed.emit()

    def _on_toggle(self, checked):
        ok = self.manager.request_enable(MODULE_POT, checked)
        if checked and not ok:
            self.header.set_checked_silently(False)
        self.changed.emit()

    def _on_loop(self, value):
        self.module.set_loop_ms(value)
        self.changed.emit()

    # ------------------------------------------------------------------ veri
    def apply(self):
        self.module.set_config({name: row.values() for name, row in self.rows.items()})

    def action_keys(self):
        return [row.action_key() for row in self.rows.values() if row.action_key()]

    def to_dict(self) -> dict:
        data = {name: row.values() for name, row in self.rows.items()}
        data["enabled"] = self.header.is_checked()
        data["hotkey"] = self.header.hotkey_value()
        data["loop_ms"] = self.header.loop_ms()
        return data

    def from_dict(self, data):
        data = data or {}
        for name, row in self.rows.items():
            row.blockSignals(True)
            row.set_values(data.get(name))
            row.blockSignals(False)
        self.header.set_hotkey(data.get("hotkey", ""))
        self.header.set_loop_ms(data.get("loop_ms", DEFAULT_LOOP_MS["pot"]))
        self.module.set_loop_ms(self.header.loop_ms())
        self.header.set_checked_silently(bool(data.get("enabled", False)))
        self.apply()

    def pending_enabled(self) -> bool:
        return self.header.is_checked()

    def set_state(self, state):
        self.header.set_state(state)

    def force_unchecked(self):
        self.header.set_checked_silently(False)
