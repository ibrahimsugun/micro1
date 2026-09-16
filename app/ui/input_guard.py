"""Yanlışlıkla ayar değiştirmeyi önleyen girdi koruması.

Sorun: fare tekerleğiyle paneli kaydırırken imleç bir açılır kutu / sayaç /
kaydırıcı üzerine denk gelirse, Qt varsayılanı o widget'ın DEĞERİNİ değiştirir
(skill tuşu, eşik, yüzde...). Kullanıcı farkında olmadan ayarları bozuyordu.

Çözüm: bu widget'lar ODAKTA DEĞİLKEN gelen tekerlek olayı değeri değiştirmez;
en yakın kaydırma alanına iletilir (panel normal kayar). Kullanıcı önce
TIKLAYIP odakladığında tekerlekle değer değiştirebilir. Böylece değişiklik
yalnızca bilinçli tıklamayla olur.
"""

from PyQt5.QtCore import QEvent, QObject
from PyQt5.QtWidgets import (
    QAbstractSlider,
    QAbstractSpinBox,
    QComboBox,
    QScrollArea,
)


class WheelGuard(QObject):
    """Uygulama geneli olay süzgeci: odaksız tekerleği kaydırmaya çevirir."""

    _WIDGETS = (QComboBox, QAbstractSpinBox, QAbstractSlider)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and isinstance(obj, self._WIDGETS):
            if not obj.hasFocus():
                # Değeri değiştirme; onun yerine paneli kaydır. Olayı viewport'a
                # yeniden GÖNDERMEK süzgeci tekrar tetikleyip sonsuz döngü yapar;
                # bu yüzden kaydırma çubuğunu DOĞRUDAN oynatıyoruz.
                area = self._scroll_area(obj)
                if area is not None:
                    delta = event.angleDelta().y()
                    if delta:
                        bar = area.verticalScrollBar()
                        bar.setValue(bar.value() - delta)
                return True            # widget değerini DEĞİŞTİRME
        return False

    @staticmethod
    def _scroll_area(widget):
        parent = widget.parent()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                return parent
            parent = parent.parent()
        return None


def install_input_guards(app):
    """Uygulamaya girdi korumasını tak. Süzgeç referansı app'te tutulur."""
    guard = WheelGuard(app)
    app.installEventFilter(guard)
    app._wheel_guard = guard           # GC olmasın diye referans
    return guard
