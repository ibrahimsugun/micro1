"""Modül durum panosu: her modül için renkli nokta + durum metni."""

from PyQt5.QtWidgets import QGridLayout, QLabel

from ...constants import (
    MODULE_ATTACK,
    MODULE_BUFF,
    MODULE_CLICKER,
    MODULE_HEAL,
    MODULE_POT,
)
from ...core.module_base import STATE_LABELS
from ..theme import MUTED, state_color
from .card import Card
from .common import StatusDot

BOARD_ORDER = [MODULE_POT, MODULE_ATTACK, MODULE_HEAL, MODULE_BUFF, MODULE_CLICKER]

# Panoda kısa adlar: sekme adlarıyla aynı dili konuşur.
BOARD_LABELS = {
    MODULE_POT: "Genel",
    MODULE_ATTACK: "Atak",
    MODULE_HEAL: "Heal",
    MODULE_BUFF: "Buff",
    MODULE_CLICKER: "Tıklayıcı",
}


class StatusBoardWidget(Card):
    def __init__(self, parent=None):
        super().__init__("Modül durumu", parent)
        self.setToolTip(
            "Yeşil: çalışıyor. Turuncu: açık ama bekliyor (master kapalı, oyun "
            "odakta değil vb). Kırmızı: durdu veya hata verdi."
        )
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(3)
        self._dots = {}
        self._labels = {}
        for row, module_id in enumerate(BOARD_ORDER):
            dot = StatusDot(self)
            name = QLabel(BOARD_LABELS[module_id], self)
            value = QLabel("Durdu", self)
            value.setStyleSheet("color: {};".format(MUTED))
            grid.addWidget(dot, row, 0)
            grid.addWidget(name, row, 1)
            grid.addWidget(value, row, 2)
            self._dots[module_id] = dot
            self._labels[module_id] = value
        grid.setColumnStretch(2, 1)
        self.add_layout(grid)

    def set_state(self, module_id, state, detail=""):
        if module_id not in self._dots:
            return
        self._dots[module_id].set_state(state)
        text = STATE_LABELS.get(state, state)
        if detail and state in ("waiting", "error"):
            text = "{} · {}".format(text, detail)
        label = self._labels[module_id]
        label.setText(text)
        label.setStyleSheet("color: {};".format(state_color(state)))
