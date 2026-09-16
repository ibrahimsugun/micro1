"""Kart ve bölüm başlığı: QGroupBox'ın ağır çerçevesi yerine kullanılır.

Kart = beyaz yüzey + ince yumuşak kenarlık. Başlık kartın İÇİNDE, küçük ve
soluk; böylece göz önce içeriğe gider.
"""

from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..theme import CARD_MARGIN, CARD_SPACING, ROW_SPACING


class SectionTitle(QLabel):
    """Kart içi küçük bölüm başlığı (büyük harf, soluk)."""

    def __init__(self, text, parent=None):
        super().__init__(text.upper(), parent)
        self.setObjectName("sectionTitle")


class Divider(QFrame):
    """1 px yatay ayraç."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("divider")
        self.setFrameShape(QFrame.NoFrame)


class Card(QFrame):
    """Başlıklı içerik kartı.

    İçeriği `content` düzenine eklenir; `add()` / `add_layout()` kısayolları
    vardır. Böylece tüm sekmelerde aynı iç boşluk ve ritim korunur.
    """

    def __init__(self, title=None, parent=None, flat=False):
        super().__init__(parent)
        self.setObjectName("cardFlat" if flat else "card")
        self.content = QVBoxLayout(self)
        self.content.setContentsMargins(
            CARD_MARGIN, CARD_MARGIN - 2, CARD_MARGIN, CARD_MARGIN
        )
        self.content.setSpacing(CARD_SPACING)
        self.title_label = None
        if title:
            self.title_label = SectionTitle(title, self)
            self.content.addWidget(self.title_label)

    def add(self, widget, stretch=0):
        self.content.addWidget(widget, stretch)
        return widget

    def add_layout(self, layout):
        self.content.addLayout(layout)
        return layout

    def add_divider(self):
        self.content.addWidget(Divider(self))

    def set_title(self, text):
        if self.title_label is not None:
            self.title_label.setText(text.upper())


def field_row(*widgets, spacing=ROW_SPACING):
    """Yatay alan satırı: [etiket] [girdi] [girdi] ..."""
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for item in widgets:
        if item is None:
            layout.addStretch(1)
        elif isinstance(item, QWidget):
            layout.addWidget(item)
        else:
            layout.addLayout(item)
    return layout


def field_label(text, parent=None):
    label = QLabel(text, parent)
    label.setObjectName("fieldLabel")
    return label


def hint_label(text, parent=None):
    label = QLabel(text, parent)
    label.setObjectName("hint")
    label.setWordWrap(True)
    return label
