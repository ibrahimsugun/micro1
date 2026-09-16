"""Priest sekmesi: tekli heal, parti heal ve 6 satırlık buff bölümü.

Heal ve buff AYRI modüllerdir: ayrı tık, ayrı kısayol, ayrı döngü hızı.
Buff hücreleri 2 sütun x 3 satır ızgarasına yerleşir (kullanıcı kararı).
"""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...constants import (
    DEFAULT_LOOP_MS,
    HEAL_MEMBER_COOLDOWN_MS,
    MAX_PARTY_MEMBERS,
    MODULE_BUFF,
    MODULE_HEAL,
)
from ...modules.buff_module import BUFF_ROW_COUNT
from ..theme import CARD_SPACING
from ..widgets.buff_row_widget import BuffRowWidget
from ..widgets.card import Card, field_label, field_row
from ..widgets.common import ActionKeyCombo, PageCombo, PercentSpin
from ..widgets.module_header import ModuleHeader


class PriestTab(QWidget):
    changed = pyqtSignal()
    partyCountChanged = pyqtSignal(object)   # None = otomatik, 0 = solo, 1-8 = sabit

    def __init__(self, manager, hotkey_service, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.heal = manager.get(MODULE_HEAL)
        self.buff = manager.get(MODULE_BUFF)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(CARD_SPACING + 1)

        # ------------------------------------------------------------- heal
        self.heal_header = ModuleHeader(
            "Priest · heal", MODULE_HEAL, hotkey_service,
            DEFAULT_LOOP_MS["heal"], self,
        )
        root.addWidget(self.heal_header)

        single_box = Card("Tekli heal", self)
        single_box.setToolTip(
            "Tek bir ortak yüzde eşiği kullanır. 'Partiye bas' kapalıyken "
            "yalnızca kendi HP'ne bakar ve tıklama yapmaz."
        )
        self.single_check = QCheckBox("Aktif", single_box)
        self.single_check.setToolTip("Tekli heal satırını aç/kapa.")
        self.single_threshold = PercentSpin(
            70, single_box,
            tooltip="Bu yüzdenin altına düşen hedefe heal basılır.",
        )
        self.single_key = ActionKeyCombo(single_box)
        self.single_page = PageCombo(single_box)
        single_box.add_layout(field_row(
            self.single_check, None, self.single_threshold,
            self.single_key, self.single_page, spacing=5,
        ))

        self.party_click_check = QCheckBox("Partiye bas", single_box)
        self.party_click_check.setToolTip(
            "Açıkken eşik altındaki EN DÜŞÜK HP'li üyenin satır merkezine TEK "
            "tık atılır ve heal tuşuna basılır. Aynı üyeye {} ms içinde tekrar "
            "basılmaz. Fare tıklanan yerde kalır.".format(HEAL_MEMBER_COOLDOWN_MS)
        )
        single_box.add(self.party_click_check)
        root.addWidget(single_box)

        party_box = Card("Parti heal", self)
        party_box.setToolTip(
            "Eşik altındaki üye sayısı tetik değerine ulaşınca en düşük HP'li "
            "üyeye tıklanıp parti heal tuşuna basılır."
        )
        self.party_check = QCheckBox("Aktif", party_box)
        self.party_check.setToolTip("Parti heal satırını aç/kapa.")
        self.party_threshold = PercentSpin(
            60, party_box,
            tooltip="Üyeler bu yüzdenin altına düşünce sayılır.",
        )
        self.party_key = ActionKeyCombo(party_box)
        self.party_page = PageCombo(party_box)
        party_box.add_layout(field_row(
            self.party_check, None, self.party_threshold,
            self.party_key, self.party_page, spacing=5,
        ))

        self.party_trigger = QSpinBox(party_box)
        self.party_trigger.setRange(1, MAX_PARTY_MEMBERS)
        self.party_trigger.setValue(3)
        self.party_trigger.setFixedWidth(58)
        self.party_trigger.setToolTip(
            "Kaç üye eşiğin altına düştüğünde parti heal atılsın."
        )
        party_box.add_layout(field_row(
            field_label("Tetik üye sayısı", party_box), None, self.party_trigger
        ))

        # Üye sayısı: otomatik sayım bu işin en zor görüntü problemi (boş
        # satırın arkası oyun dünyasıdır) ve sayıyı kullanıcı zaten biliyor.
        # Elle verilince sayım maliyeti de hata riski de sıfırlanır; Solo
        # seçilirse parti hiç okunmaz.
        self.party_count = QComboBox(party_box)
        self.party_count.addItem("Otomatik", None)
        self.party_count.addItem("Solo (parti yok)", 0)
        for n in range(1, MAX_PARTY_MEMBERS + 1):
            self.party_count.addItem("{} kişi".format(n), n)
        self.party_count.setFixedWidth(120)
        self.party_count.setToolTip(
            "Partide kaç kişi olduğunu elle söyle: yalnız o kadar satır okunur.\n"
            "Solo seçilirse parti hiç okunmaz. Otomatik sayım oyun dünyasını "
            "üye sanabilir, bu yüzden elle vermek daha güvenilirdir."
        )
        party_box.add_layout(field_row(
            field_label("Üye sayısı", party_box), None, self.party_count
        ))
        root.addWidget(party_box)

        # ------------------------------------------------------------- buff
        self.buff_header = ModuleHeader(
            "Priest · buff", MODULE_BUFF, hotkey_service,
            DEFAULT_LOOP_MS["buff"], self,
        )
        self.buff_header.setToolTip(
            "Buff modülü heal tikinden BAĞIMSIZDIR; ayrı açılıp kapanır."
        )
        root.addWidget(self.buff_header)

        buff_box = Card("Buff satırları", self)
        buff_grid = QGridLayout()
        buff_grid.setContentsMargins(0, 0, 0, 0)
        buff_grid.setHorizontalSpacing(8)
        buff_grid.setVerticalSpacing(6)
        self.buff_rows = []
        for i in range(BUFF_ROW_COUNT):
            row = BuffRowWidget(i, buff_box)
            row.changed.connect(self._on_buff_changed)
            self.buff_rows.append(row)
            buff_grid.addWidget(row, i // 2, i % 2)   # 2×2 yerleşim
        buff_grid.setColumnStretch(0, 1)
        buff_grid.setColumnStretch(1, 1)
        buff_box.add_layout(buff_grid)
        root.addWidget(buff_box)
        root.addStretch(1)

        for widget in (self.single_check, self.party_click_check, self.party_check):
            widget.toggled.connect(self._on_heal_changed)
        for widget in (self.single_key, self.single_page, self.party_key,
                       self.party_page):
            widget.currentIndexChanged.connect(self._on_heal_changed)
        self.single_threshold.valueChanged.connect(self._on_heal_changed)
        self.party_threshold.valueChanged.connect(self._on_heal_changed)
        self.party_trigger.valueChanged.connect(self._on_heal_changed)
        self.party_count.currentIndexChanged.connect(self._on_party_count)

        self.heal_header.enabledChanged.connect(self._on_heal_toggle)
        self.heal_header.hotkeyChanged.connect(lambda _: self.changed.emit())
        self.heal_header.loopChanged.connect(self._on_heal_loop)
        self.buff_header.enabledChanged.connect(self._on_buff_toggle)
        self.buff_header.hotkeyChanged.connect(lambda _: self.changed.emit())
        self.buff_header.loopChanged.connect(self._on_buff_loop)

    # ------------------------------------------------------------------ olaylar
    def _on_heal_changed(self, *_args):
        self.apply_heal()
        self.changed.emit()

    def _on_buff_changed(self, *_args):
        self.apply_buff()
        self.changed.emit()

    def _on_heal_toggle(self, checked):
        ok = self.manager.request_enable(MODULE_HEAL, checked)
        if checked and not ok:
            self.heal_header.set_checked_silently(False)
        self.changed.emit()

    def _on_buff_toggle(self, checked):
        ok = self.manager.request_enable(MODULE_BUFF, checked)
        if checked and not ok:
            self.buff_header.set_checked_silently(False)
        self.changed.emit()

    def _on_heal_loop(self, value):
        self.heal.set_loop_ms(value)
        self.changed.emit()

    def _on_buff_loop(self, value):
        self.buff.set_loop_ms(value)
        self.changed.emit()

    # ------------------------------------------------------------------ veri
    def _heal_config(self) -> dict:
        return {
            "single": {
                "enabled": self.single_check.isChecked(),
                "threshold": self.single_threshold.value(),
                "key": self.single_key.key(),
                "fpage": self.single_page.page(),
                "party_click": self.party_click_check.isChecked(),
            },
            "party": {
                "enabled": self.party_check.isChecked(),
                "threshold": self.party_threshold.value(),
                "key": self.party_key.key(),
                "fpage": self.party_page.page(),
                "trigger_count": self.party_trigger.value(),
            },
        }

    def party_count_value(self):
        """None = otomatik, 0 = solo, 1-8 = sabit üye sayısı."""
        return self.party_count.currentData()

    def _on_party_count(self):
        self.partyCountChanged.emit(self.party_count_value())
        self.changed.emit()

    def apply_heal(self):
        self.heal.set_config(self._heal_config())

    def apply_buff(self):
        self.buff.set_rows([row.values() for row in self.buff_rows])

    def apply(self):
        self.apply_heal()
        self.apply_buff()

    def action_keys(self):
        keys = [self.single_key.key(), self.party_key.key()]
        keys.extend(row.action_key() for row in self.buff_rows)
        return [k for k in keys if k]

    def refresh_buff_timers(self):
        for row, remaining in zip(self.buff_rows, self.buff.remaining_seconds()):
            row.set_remaining(remaining)

    def to_dict(self) -> dict:
        data = self._heal_config()
        data["party_count"] = self.party_count_value()
        data["heal_enabled"] = self.heal_header.is_checked()
        data["heal_hotkey"] = self.heal_header.hotkey_value()
        data["heal_loop_ms"] = self.heal_header.loop_ms()
        data["buffs"] = [row.values() for row in self.buff_rows]
        data["buff_enabled"] = self.buff_header.is_checked()
        data["buff_hotkey"] = self.buff_header.hotkey_value()
        data["buff_loop_ms"] = self.buff_header.loop_ms()
        return data

    def from_dict(self, data):
        data = data or {}
        single = data.get("single") or {}
        party = data.get("party") or {}

        index = self.party_count.findData(data.get("party_count", None))
        self.party_count.blockSignals(True)
        self.party_count.setCurrentIndex(index if index >= 0 else 0)
        self.party_count.blockSignals(False)

        for widget, value in (
            (self.single_check, single.get("enabled", False)),
            (self.party_click_check, single.get("party_click", False)),
            (self.party_check, party.get("enabled", False)),
        ):
            widget.blockSignals(True)
            widget.setChecked(bool(value))
            widget.blockSignals(False)

        for widget, value in ((self.single_key, single.get("key", "")),
                              (self.party_key, party.get("key", ""))):
            widget.blockSignals(True)
            widget.set_key(value)
            widget.blockSignals(False)
        for widget, value in ((self.single_page, single.get("fpage")),
                              (self.party_page, party.get("fpage"))):
            widget.blockSignals(True)
            widget.set_page(value)
            widget.blockSignals(False)
        for widget, value in (
            (self.single_threshold, int(single.get("threshold", 70))),
            (self.party_threshold, int(party.get("threshold", 60))),
        ):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)
        self.party_trigger.blockSignals(True)
        self.party_trigger.setValue(int(party.get("trigger_count", 3)))
        self.party_trigger.blockSignals(False)

        buffs = data.get("buffs") or []
        for i, row in enumerate(self.buff_rows):
            row.blockSignals(True)
            row.set_values(buffs[i] if i < len(buffs) else None)
            row.blockSignals(False)

        self.heal_header.set_hotkey(data.get("heal_hotkey", ""))
        self.heal_header.set_loop_ms(data.get("heal_loop_ms", DEFAULT_LOOP_MS["heal"]))
        self.heal.set_loop_ms(self.heal_header.loop_ms())
        self.heal_header.set_checked_silently(bool(data.get("heal_enabled", False)))

        self.buff_header.set_hotkey(data.get("buff_hotkey", ""))
        self.buff_header.set_loop_ms(data.get("buff_loop_ms", DEFAULT_LOOP_MS["buff"]))
        self.buff.set_loop_ms(self.buff_header.loop_ms())
        self.buff_header.set_checked_silently(bool(data.get("buff_enabled", False)))

        self.apply()

    def pending_heal_enabled(self) -> bool:
        return self.heal_header.is_checked()

    def pending_buff_enabled(self) -> bool:
        return self.buff_header.is_checked()

    def set_state(self, module_id, state):
        if module_id == MODULE_HEAL:
            self.heal_header.set_state(state)
        elif module_id == MODULE_BUFF:
            self.buff_header.set_state(state)

    def force_unchecked(self, module_id):
        if module_id == MODULE_HEAL:
            self.heal_header.set_checked_silently(False)
        elif module_id == MODULE_BUFF:
            self.buff_header.set_checked_silently(False)
