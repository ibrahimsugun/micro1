"""Genel sekmesindeki tek pot satırı: tık + eşik + tuş (+ F sayfası).

Tek satırlık düzen (kullanıcı kararı — kaydırıcı yerine kutu):
    [☑ HP potu] [%50] [tuş] [sayfa]
Kaydırıcı her satıra fazladan bir satır ekliyordu; kutu hem yerden kazandırıyor
hem de değeri bakışta okutuyor.
"""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QHBoxLayout, QWidget

from .common import PAGE_W, ActionKeyCombo, PageCombo, PercentSpin

ROW_GAP = 5


class PotRowWidget(QWidget):
    changed = pyqtSignal()

    def __init__(self, caption, tooltip="", with_page=True, default_threshold=50,
                 parent=None):
        super().__init__(parent)
        self.with_page = with_page

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(ROW_GAP)

        self.check = QCheckBox(caption, self)
        if tooltip:
            self.check.setToolTip(tooltip)
        row.addWidget(self.check, 1)

        self.threshold = PercentSpin(
            default_threshold, self,
            tooltip="Bu yüzdenin ALTINA düşünce tuşa basılır.",
        )
        row.addWidget(self.threshold)

        self.key_combo = ActionKeyCombo(self)
        row.addWidget(self.key_combo)

        if with_page:
            self.page_combo = PageCombo(self)
            row.addWidget(self.page_combo)
        else:
            self.page_combo = None
            # Sayfası olmayan satırda kutular yine sağda hizalı dursun.
            # (Genişlik sabitten alınır; buraya kutu KOYULMAZ.)
            spacer = QWidget(self)
            spacer.setFixedWidth(PAGE_W)
            spacer.setStyleSheet("background: transparent;")
            row.addWidget(spacer)

        self.check.toggled.connect(lambda _: self.changed.emit())
        self.key_combo.currentIndexChanged.connect(lambda _: self.changed.emit())
        self.threshold.valueChanged.connect(lambda _: self.changed.emit())
        if self.page_combo is not None:
            self.page_combo.currentIndexChanged.connect(lambda _: self.changed.emit())

    # ------------------------------------------------------------------ veri
    def values(self) -> dict:
        data = {
            "enabled": self.check.isChecked(),
            "threshold": self.threshold.value(),
            "key": self.key_combo.key(),
        }
        if self.page_combo is not None:
            data["fpage"] = self.page_combo.page()
        return data

    def set_values(self, data):
        data = data or {}
        self.check.setChecked(bool(data.get("enabled", False)))
        self.threshold.setValue(int(data.get("threshold", 50)))
        self.key_combo.set_key(data.get("key", ""))
        if self.page_combo is not None:
            self.page_combo.set_page(data.get("fpage"))

    def action_key(self) -> str:
        return self.key_combo.key()
