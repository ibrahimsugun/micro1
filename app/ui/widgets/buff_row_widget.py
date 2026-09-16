"""Priest sekmesindeki tek buff hücresi: tık + tuş + F sayfası + süre.

Hücreler 2 sütun x 3 satır ızgarasına yerleşir (kullanıcı kararı), bu yüzden
kutular sekmenin genelinden bir tık dardır ve iki satıra bölünmüştür:
    [☐] [tuş] [sayfa]
    [süre]          [kalan]
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..theme import FAINT
from .common import ActionKeyCombo, PageCombo

BUFF_KEY_W = 40
BUFF_PAGE_W = 48


class BuffRowWidget(QWidget):
    changed = pyqtSignal()

    def __init__(self, index, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(3)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(5)
        root.addLayout(top)

        # Sıra numarası ızgaradaki konumdan belli; tikte yazı yok.
        self.check = QCheckBox(self)
        self.check.setToolTip("{}. buff satırı çalışsın mı?".format(index + 1))
        top.addWidget(self.check)

        self.key_combo = ActionKeyCombo(self)
        self.key_combo.setFixedWidth(BUFF_KEY_W)
        top.addWidget(self.key_combo)

        self.page_combo = PageCombo(self)
        self.page_combo.setFixedWidth(BUFF_PAGE_W)
        top.addWidget(self.page_combo)
        top.addStretch(1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(5)
        root.addLayout(bottom)

        self.duration = QSpinBox(self)
        self.duration.setRange(1, 7200)
        self.duration.setValue(600)
        self.duration.setSuffix(" sn")
        self.duration.setFixedWidth(68)
        self.duration.setToolTip(
            "Buff süresi. Sayaç dolunca tuşa tekrar basılır. Her satırın sayacı "
            "bağımsızdır; parti değişikliği sayacı sıfırlamaz."
        )
        bottom.addWidget(self.duration)

        # Kalan süre süre kutusunun HEMEN yanında dursun: araya esneme
        # koymak ikisini pencerenin iki ucuna itiyordu.
        self.remaining = QLabel("—", self)
        self.remaining.setFixedWidth(34)
        self.remaining.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.remaining.setStyleSheet("color: {}; font-size: 11px;".format(FAINT))
        self.remaining.setToolTip("Bu buff için kalan süre.")
        bottom.addWidget(self.remaining)
        bottom.addStretch(1)

        self.check.toggled.connect(lambda _: self.changed.emit())
        self.key_combo.currentIndexChanged.connect(lambda _: self.changed.emit())
        self.page_combo.currentIndexChanged.connect(lambda _: self.changed.emit())
        self.duration.valueChanged.connect(lambda _: self.changed.emit())

    def values(self) -> dict:
        return {
            "enabled": self.check.isChecked(),
            "key": self.key_combo.key(),
            "fpage": self.page_combo.page(),
            "duration": self.duration.value(),
        }

    def set_values(self, data):
        data = data or {}
        self.check.setChecked(bool(data.get("enabled", False)))
        self.key_combo.set_key(data.get("key", ""))
        self.page_combo.set_page(data.get("fpage"))
        self.duration.setValue(int(data.get("duration", 600)))

    def set_remaining(self, seconds):
        self.remaining.setText("—" if seconds is None else "{}sn".format(int(seconds)))

    def action_key(self) -> str:
        return self.key_combo.key()
