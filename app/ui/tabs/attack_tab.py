"""Atak sekmesi: skill sırası, gecikme, R sayacı, RPR ve Z ayarları."""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QSpinBox, QVBoxLayout, QWidget

from ...constants import (
    ATTACK_RANDOM_MAX_DEFAULT,
    DEFAULT_LOOP_MS,
    MODULE_ATTACK,
    R_ATTACK_INTERVAL_MS,
    RPR_REPEAT_MS,
    Z_MAX_MS,
    Z_MIN_MS,
)
from ...modules.attack_module import SKILL_ROW_COUNT
from ..theme import CARD_SPACING
from ..widgets.card import Card, field_label, field_row, hint_label
from ..widgets.common import ActionKeyCombo, PageCombo
from ..widgets.module_header import ModuleHeader
from ..widgets.skill_row_widget import SkillRowWidget


class AttackTab(QWidget):
    changed = pyqtSignal()

    def __init__(self, manager, hotkey_service, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.module = manager.get(MODULE_ATTACK)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(CARD_SPACING + 1)

        self.header = ModuleHeader(
            "Atak", MODULE_ATTACK, hotkey_service, DEFAULT_LOOP_MS["attack"], self
        )
        root.addWidget(self.header)

        # --- skill sırası ---------------------------------------------------
        skills_box = Card("Skill sırası", self)
        skills_box.setToolTip(
            "Skiller listedeki sırayla basılır. Sırayı yukarı/aşağı oklarıyla "
            "değiştir. Hedef yokken skill döngüsü durur."
        )
        self.skills_layout = QVBoxLayout()
        self.skills_layout.setContentsMargins(0, 0, 0, 0)
        self.skills_layout.setSpacing(4)
        self.skill_rows = []
        for i in range(SKILL_ROW_COUNT):
            row = SkillRowWidget(i, skills_box)
            row.changed.connect(self._on_changed)
            row.moveUp.connect(self._move_up)
            row.moveDown.connect(self._move_down)
            self.skill_rows.append(row)
            self.skills_layout.addWidget(row)
        skills_box.add_layout(self.skills_layout)
        root.addWidget(skills_box)

        # --- zamanlama ------------------------------------------------------
        timing_box = Card("Gecikme", self)
        self.delay_spin = QSpinBox(timing_box)
        self.delay_spin.setRange(0, 20000)
        self.delay_spin.setValue(800)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.setFixedWidth(90)
        self.delay_spin.setToolTip(
            "İki skill arasındaki temel bekleme. Rastgele tiki kapalı olsa bile "
            "otomatik olarak ±%10 doğal sapma uygulanır."
        )
        timing_box.add_layout(field_row(
            field_label("Skill aralığı", timing_box), None, self.delay_spin
        ))

        self.random_check = QCheckBox("Rastgele ekle", timing_box)
        self.random_check.setChecked(True)
        self.random_check.setToolTip(
            "Açıkken temel gecikmeye 0 ile aşağıdaki üst sınır arasında "
            "rastgele bir süre eklenir."
        )
        self.random_spin = QSpinBox(timing_box)
        self.random_spin.setRange(0, 20000)
        self.random_spin.setValue(ATTACK_RANDOM_MAX_DEFAULT)
        self.random_spin.setSuffix(" ms")
        self.random_spin.setFixedWidth(90)
        self.random_spin.setToolTip("Eklenecek rastgele sürenin üst sınırı.")
        timing_box.add_layout(field_row(self.random_check, None, self.random_spin))

        root.addWidget(timing_box)

        # --- R / RPR / Z ----------------------------------------------------
        extra_box = Card("R, RPR ve hedef", self)
        self.r_check = QCheckBox("R atak", extra_box)
        self.r_check.setChecked(True)
        self.r_check.setToolTip(
            "Hedef varken sabit {} ms aralıklarla R basar. Hedef yokken R de "
            "durur.".format(R_ATTACK_INTERVAL_MS)
        )
        extra_box.add(self.r_check)

        self.rpr_check = QCheckBox("RPR (çekiç)", extra_box)
        self.rpr_check.setToolTip(
            "Silah yanınca çekiç tuşuna BİR KEZ basar; hâlâ yanıksa {} sn "
            "sonra tekrar dener.".format(RPR_REPEAT_MS // 1000)
        )
        self.rpr_key = ActionKeyCombo(extra_box)
        self.rpr_page = PageCombo(extra_box)
        extra_box.add_layout(field_row(
            self.rpr_check, None, self.rpr_key, self.rpr_page
        ))

        self.no_z_check = QCheckBox("Mob ölmeden Z yapma", extra_box)
        self.no_z_check.setToolTip(
            "Açıkken hedef barı boşalmadan (mob ölmeden) yeni Z basılmaz.\n"
            "Kapalıyken mob'a vururken de belirli aralıklarla Z basılır.")
        extra_box.add(self.no_z_check)
        extra_box.add(hint_label(
            "Z aralığı: {}-{} ms (rastgele).".format(Z_MIN_MS, Z_MAX_MS),
            extra_box,
        ))
        root.addWidget(extra_box)
        root.addStretch(1)

        for widget in (self.delay_spin, self.random_spin):
            widget.valueChanged.connect(self._on_changed)
        for widget in (self.random_check, self.r_check, self.rpr_check,
                       self.no_z_check):
            widget.toggled.connect(self._on_changed)
        for widget in (self.rpr_key, self.rpr_page):
            widget.currentIndexChanged.connect(self._on_changed)

        self.header.enabledChanged.connect(self._on_toggle)
        self.header.hotkeyChanged.connect(lambda _: self.changed.emit())
        self.header.loopChanged.connect(self._on_loop)

    # ------------------------------------------------------------------ sıra
    def _reindex(self):
        for i, row in enumerate(self.skill_rows):
            row.set_order(i)

    def _swap(self, index_a, index_b):
        rows = self.skill_rows
        rows[index_a], rows[index_b] = rows[index_b], rows[index_a]
        for i, row in enumerate(rows):
            self.skills_layout.insertWidget(i, row)
        self._reindex()
        self._on_changed()

    def _move_up(self, row):
        index = self.skill_rows.index(row)
        if index > 0:
            self._swap(index, index - 1)

    def _move_down(self, row):
        index = self.skill_rows.index(row)
        if index < len(self.skill_rows) - 1:
            self._swap(index, index + 1)

    # ------------------------------------------------------------------ olaylar
    def _on_changed(self, *_args):
        self.apply()
        self.changed.emit()

    def _on_toggle(self, checked):
        ok = self.manager.request_enable(MODULE_ATTACK, checked)
        if checked and not ok:
            self.header.set_checked_silently(False)
        self.changed.emit()

    def _on_loop(self, value):
        self.module.set_loop_ms(value)
        self.changed.emit()

    # ------------------------------------------------------------------ veri
    def _config(self) -> dict:
        return {
            "skills": [row.values() for row in self.skill_rows],
            "delay_ms": self.delay_spin.value(),
            "random_enabled": self.random_check.isChecked(),
            "random_max": self.random_spin.value(),
            "r_enabled": self.r_check.isChecked(),
            "rpr_enabled": self.rpr_check.isChecked(),
            "rpr_key": self.rpr_key.key(),
            "rpr_fpage": self.rpr_page.page(),
            "no_z_until_dead": self.no_z_check.isChecked(),
        }

    def apply(self):
        self.module.set_config(self._config())

    def action_keys(self):
        keys = [row.action_key() for row in self.skill_rows if row.action_key()]
        if self.rpr_key.key():
            keys.append(self.rpr_key.key())
        keys.extend(["R", "Z"])
        return keys

    def to_dict(self) -> dict:
        data = self._config()
        data["enabled"] = self.header.is_checked()
        data["hotkey"] = self.header.hotkey_value()
        data["loop_ms"] = self.header.loop_ms()
        return data

    def from_dict(self, data):
        data = data or {}
        skills = data.get("skills") or []
        for i, row in enumerate(self.skill_rows):
            row.blockSignals(True)
            row.set_values(skills[i] if i < len(skills) else None)
            row.blockSignals(False)
        self._reindex()

        for widget, key, default in (
            (self.delay_spin, "delay_ms", 800),
            (self.random_spin, "random_max", ATTACK_RANDOM_MAX_DEFAULT),
        ):
            widget.blockSignals(True)
            widget.setValue(int(data.get(key, default)))
            widget.blockSignals(False)
        for widget, key, default in (
            (self.random_check, "random_enabled", True),
            (self.r_check, "r_enabled", True),
            (self.rpr_check, "rpr_enabled", False),
            (self.no_z_check, "no_z_until_dead", False),
        ):
            widget.blockSignals(True)
            widget.setChecked(bool(data.get(key, default)))
            widget.blockSignals(False)
        self.rpr_page.blockSignals(True)
        self.rpr_page.set_page(data.get("rpr_fpage"))
        self.rpr_page.blockSignals(False)
        self.rpr_key.blockSignals(True)
        self.rpr_key.set_key(data.get("rpr_key", ""))
        self.rpr_key.blockSignals(False)

        self.header.set_hotkey(data.get("hotkey", ""))
        self.header.set_loop_ms(data.get("loop_ms", DEFAULT_LOOP_MS["attack"]))
        self.module.set_loop_ms(self.header.loop_ms())
        self.header.set_checked_silently(bool(data.get("enabled", False)))
        self.apply()

    def pending_enabled(self) -> bool:
        return self.header.is_checked()

    def set_state(self, state):
        self.header.set_state(state)

    def force_unchecked(self):
        self.header.set_checked_silently(False)
