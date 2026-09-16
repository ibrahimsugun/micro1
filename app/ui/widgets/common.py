"""Sekmelerde tekrar eden küçük denetimler.

Genişlikler tek yerden yönetilir (KEY_W / PAGE_W / PCT_W): panel ölçüsü
değişirse burada bir satır değiştirmek yeter, satır bileşenleri kaymaz.
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QWidget,
)

from ...constants import ACTION_KEYS, F_PAGES, NO_PAGE
from ...services.hotkey_service import display_name
from ..theme import (
    AMBER,
    FAINT,
    GREEN,
    MUTED,
    RED,
    TEXT,
    state_color,
)

# Satır bileşenlerinin ortak genişlikleri
KEY_W = 50       # tuş kutusu (yalnız 1-0 rakamları)
PAGE_W = 62      # F sayfası kutusu
PCT_W = 38       # yüzde etiketi
PCT_SPIN_W = 56  # yüzde eşiği kutusu


class ActionKeyCombo(QComboBox):
    """Oyuna gönderilecek tuş (hızlı erişim çubuğu rakamları)."""

    def __init__(self, parent=None, allow_empty=True):
        super().__init__(parent)
        if allow_empty:
            self.addItem("—")
        self.addItems(ACTION_KEYS)
        self.setFixedWidth(KEY_W)
        self.setToolTip(
            "Oyuna gönderilecek tuş. Hızlı erişim çubuğu rakamları (1-0)."
        )

    def key(self) -> str:
        text = self.currentText()
        return "" if text == "—" else text

    def set_key(self, value):
        value = (value or "").upper()
        index = self.findText(value) if value else 0
        self.setCurrentIndex(index if index >= 0 else 0)


class PageCombo(QComboBox):
    """F sayfası seçimi.

    Saklanan değer değişmedi (NO_PAGE = "F Sayfası" = geçiş yapma); listede
    o seçenek "Yok" olarak görünür, değer userData'da tutulur.
    """

    NO_PAGE_DISPLAY = "Yok"

    def __init__(self, parent=None):
        super().__init__(parent)
        for value in F_PAGES:
            self.addItem(
                self.NO_PAGE_DISPLAY if value == NO_PAGE else value, value
            )
        self.setFixedWidth(PAGE_W)
        self.setToolTip(
            "Tuşa basmadan önce geçilecek F sayfası. 'Yok' seçilirse geçiş "
            "yapılmaz. Geçişten sonra 100 ms beklenir, geri dönüş yoktur."
        )

    def page(self) -> str:
        value = self.currentData()
        return value if value is not None else NO_PAGE

    def set_page(self, value):
        index = self.findData(value or NO_PAGE)
        self.setCurrentIndex(index if index >= 0 else 0)


class PercentLabel(QLabel):
    """Yüzde göstergesi; kaydırıcıdan ayrı yerleştirilebilir."""

    def __init__(self, value=0, parent=None):
        super().__init__("%{}".format(int(value)), parent)
        self.setFixedWidth(PCT_W)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setStyleSheet("color: {}; font-weight: 700;".format(TEXT))


class PercentSpin(QSpinBox):
    """Yüzde eşiği KUTUSU.

    Kaydırıcının yerini aldı (kullanıcı kararı): kaydırıcı bir satırı tek
    başına yiyordu, kutu sayesinde tik + eşik + tuş + F sayfası tek satıra
    sığıyor ve değer bakışta okunuyor.
    """

    def __init__(self, value=50, parent=None, tooltip=""):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setPrefix("%")
        self.setValue(int(value))
        self.setFixedWidth(PCT_SPIN_W)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if tooltip:
            self.setToolTip(tooltip)

    def value_percent(self) -> int:
        return self.value()

    def set_value(self, value):
        self.setValue(int(value))


class PercentSlider(QWidget):
    """Yüzde eşiği kaydırıcısı (anket kararı: kutu değil kaydırıcı).

    Etiket ayrı bir bileşendir; istenirse başka bir satıra taşınabilir
    (pot satırlarında tuş kutusunun soluna alınıyor).
    """

    valueChanged = pyqtSignal(int)

    def __init__(self, value=50, parent=None, tooltip="", show_label=True):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setRange(0, 100)
        self.slider.setValue(int(value))
        self.slider.setMinimumWidth(80)
        self.label = PercentLabel(value, self)
        layout.addWidget(self.slider, 1)
        if show_label:
            layout.addWidget(self.label)
        self.slider.valueChanged.connect(self._on_change)
        if tooltip:
            self.setToolTip(tooltip)
            self.slider.setToolTip(tooltip)

    def _on_change(self, value):
        self.label.setText("%{}".format(value))
        self.valueChanged.emit(value)

    def value(self) -> int:
        return self.slider.value()

    def set_value(self, value):
        self.slider.setValue(int(value))


class HotkeyButton(QPushButton):
    """Tıklanınca bir sonraki tuşu global kısayol olarak yakalar."""

    keyChanged = pyqtSignal(str)

    def __init__(self, caption, hotkey_service, capture_id, parent=None):
        super().__init__(parent)
        self.caption = caption
        self._service = hotkey_service
        self._capture_id = capture_id
        self._key = ""
        self._waiting = False
        self.setToolTip(
            "Tıkla ve istediğin tuşa bas. Herhangi bir tuş seçilebilir; oyun "
            "tuşlarından biriyle çakışırsa uyarılırsın."
        )
        self.clicked.connect(self._begin_capture)
        if hotkey_service is not None:
            hotkey_service.keyCaptured.connect(self._on_captured)
        self._refresh()

    def key(self) -> str:
        return self._key

    def set_key(self, value):
        self._key = (value or "").lower()
        self._refresh()

    def _refresh(self):
        if self._waiting:
            self.setText("bir tuşa bas…")
            self.setStyleSheet("color: {}; font-weight: 600;".format(GREEN))
        elif self._key:
            self.setText("{} · {}".format(self.caption, display_name(self._key)))
            self.setStyleSheet("")
        else:
            self.setText("{} · atanmadı".format(self.caption))
            self.setStyleSheet("color: {};".format(MUTED))

    def _begin_capture(self):
        if self._service is None:
            return
        self._waiting = True
        self._refresh()
        self._service.capture_next(self._capture_id)

    def _on_captured(self, capture_id, norm):
        if capture_id != self._capture_id:
            return
        self._waiting = False
        self._key = norm
        self._refresh()
        self.keyChanged.emit(norm)


class StatusDot(QLabel):
    """Yeşil = çalışıyor, turuncu = bekliyor, kırmızı = durdu/hata."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(13)
        self.setAlignment(Qt.AlignCenter)
        self.set_state("stopped")

    def set_state(self, state):
        self.setText("●")
        self.setStyleSheet(
            "color: {}; font-size: 12px;".format(state_color(state))
        )


class StatusChip(QLabel):
    """Üst şeritteki canlı değer rozeti (HP, MP, Hedef, RPR)."""

    def __init__(self, caption, parent=None):
        super().__init__(parent)
        self.caption = caption
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(22)
        self.set_value("—", TEXT)

    def set_value(self, text, color=TEXT, soft="#e4e9f1"):
        self.setText("{} {}".format(self.caption, text))
        self.setStyleSheet(
            "background-color: {}; color: {}; border-radius: 5px;"
            "font-size: 11px; font-weight: 700; padding: 3px 4px;".format(soft, color)
        )


# Eski kodun beklediği renk adları (durum metinleri için)
GREEN = GREEN
RED = RED
GRAY = MUTED
ORANGE = AMBER
