"""Sekme gezintisi: kesilmeyen, iki satırlı hap düğmeler + sayfa yığını.

Dar panelde (≈330 px) yedi sekme tek satırlık QTabBar'a sığmıyor, yazılar
"Genel" → "Gene" diye kırpılıyordu. Burada düğmeler ızgaraya dizilir, her
düğme satırı eşit böler; sekme eklemek bir satır değiştirmek kadar kolaydır.

QTabWidget'ın ana pencerede kullanılan alt kümesiyle uyumludur:
addTab / setCurrentWidget / currentWidget / currentIndex / setCurrentIndex.
"""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


def _gcd(a, b):
    while b:
        a, b = b, a % b
    return a


class NavTabs(QWidget):
    currentChanged = pyqtSignal(int)

    def __init__(self, columns=4, parent=None):
        super().__init__(parent)
        self._columns = max(1, int(columns))
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.bar = QFrame(self)
        self.bar.setObjectName("navBar")
        self._grid = QGridLayout(self.bar)
        self._grid.setContentsMargins(4, 4, 4, 4)
        self._grid.setHorizontalSpacing(3)
        self._grid.setVerticalSpacing(3)
        root.addWidget(self.bar)

        self.stack = QStackedWidget(self)
        root.addWidget(self.stack, 1)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.buttonClicked[int].connect(self.setCurrentIndex)
        self._buttons = []

    # ------------------------------------------------------------ QTabWidget API
    def addTab(self, widget, caption, tooltip=""):
        index = self.stack.addWidget(widget)
        button = QPushButton(caption, self.bar)
        button.setObjectName("navButton")
        button.setCheckable(True)
        if tooltip:
            button.setToolTip(tooltip)
        self._group.addButton(button, index)
        self._buttons.append(button)
        self._relayout()
        if index == 0:
            button.setChecked(True)
        return index

    def _relayout(self):
        """Her satır tam genişliği eşit böler (eksik son satır dahil).

        Izgara, sütun sayılarının ortak katı kadar ince sütuna bölünür;
        düğme, satırındaki düğme sayısına göre birden fazla sütun kaplar.
        """
        cols = self._columns
        total = len(self._buttons)
        units = 1
        for n in range(1, cols + 1):
            units = units * n // _gcd(units, n)
        for button in self._buttons:
            self._grid.removeWidget(button)
        for index, button in enumerate(self._buttons):
            row, col = divmod(index, cols)
            in_row = min(cols, total - row * cols)
            span = units // in_row
            self._grid.addWidget(button, row, col * span, 1, span)
        for c in range(units):
            self._grid.setColumnStretch(c, 1)

    def count(self):
        return self.stack.count()

    def currentIndex(self):
        return self.stack.currentIndex()

    def currentWidget(self):
        return self.stack.currentWidget()

    def widget(self, index):
        return self.stack.widget(index)

    def setCurrentIndex(self, index):
        if not 0 <= index < self.stack.count():
            return
        self._buttons[index].setChecked(True)
        if index != self.stack.currentIndex():
            self.stack.setCurrentIndex(index)
            self.currentChanged.emit(index)

    def setCurrentWidget(self, widget):
        index = self.stack.indexOf(widget)
        if index >= 0:
            self.setCurrentIndex(index)

    def button(self, index):
        return self._buttons[index]
