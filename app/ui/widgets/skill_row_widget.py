"""Atak sekmesindeki tek skill satırı: tık + tuş + F sayfası + sıra okları."""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QWidget

from ..theme import FAINT, ROW_SPACING
from .common import ActionKeyCombo, PageCombo


class SkillRowWidget(QWidget):
    changed = pyqtSignal()
    moveUp = pyqtSignal(object)
    moveDown = pyqtSignal(object)

    def __init__(self, index, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ROW_SPACING)

        self.check = QCheckBox(self)
        self.check.setToolTip("Bu skill sırada kullanılsın mı?")
        layout.addWidget(self.check)

        self.order_label = QLabel(str(index + 1), self)
        self.order_label.setFixedWidth(12)
        self.order_label.setStyleSheet(
            "color: {}; font-size: 11px;".format(FAINT)
        )
        self.order_label.setToolTip("Sıra numarası. Skiller bu sırayla basılır.")
        layout.addWidget(self.order_label)

        self.key_combo = ActionKeyCombo(self)
        layout.addWidget(self.key_combo)

        self.page_combo = PageCombo(self)
        layout.addWidget(self.page_combo)
        layout.addStretch(1)

        self.up_button = QPushButton("▲", self)
        self.down_button = QPushButton("▼", self)
        for button, tip in ((self.up_button, "Bu skilli sırada yukarı taşı."),
                            (self.down_button, "Bu skilli sırada aşağı taşı.")):
            button.setObjectName("iconButton")
            button.setFixedSize(22, 24)
            button.setToolTip(tip)
            layout.addWidget(button)

        self.check.toggled.connect(lambda _: self.changed.emit())
        self.key_combo.currentIndexChanged.connect(lambda _: self.changed.emit())
        self.page_combo.currentIndexChanged.connect(lambda _: self.changed.emit())
        self.up_button.clicked.connect(lambda: self.moveUp.emit(self))
        self.down_button.clicked.connect(lambda: self.moveDown.emit(self))

    def set_order(self, index):
        self.order_label.setText(str(index + 1))

    def values(self) -> dict:
        return {
            "enabled": self.check.isChecked(),
            "key": self.key_combo.key(),
            "fpage": self.page_combo.page(),
        }

    def set_values(self, data):
        data = data or {}
        self.check.setChecked(bool(data.get("enabled", False)))
        self.key_combo.set_key(data.get("key", ""))
        self.page_combo.set_page(data.get("fpage"))

    def action_key(self) -> str:
        return self.key_combo.key()
