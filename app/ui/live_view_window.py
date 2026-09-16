"""Canlı görünüm penceresi: takip edilen oyunun görüntüsü kendi içimizde.

Arka plan modunda tarayıcı kareyi doğrudan HEDEF PENCEREDEN alır; bu pencere de
aynı kareyi gösterir. Yani gösterim ile otomasyonun okuduğu görüntü TEK
KAYNAKTAN gelir — burada gördüğün, modüllerin gördüğüdür.

Neden ekrandan değil de aynı kareden: "kendi alanımızı ekrandan okumak" bu kez
BİZİM pencerenin görünür olmasını zorunlu kılardı; paylaşılan kare aynı sonucu
verir ve pencere kapatılsa/örtülse bile otomasyon çalışmaya devam eder.
"""

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import QWidget

from ..services.capture_shield import exclude_from_capture

# ~12 FPS: tarayıcı zaten 10 FPS üretiyor, daha sık çizmek boşa iş.
REFRESH_MS = 80
BACKGROUND = QColor(16, 18, 24)
TEXT_COLOR = QColor(235, 238, 245)
MUTED_COLOR = QColor(154, 164, 178)


class LiveViewWindow(QWidget):
    """Boyutlandırılabilir, ÜSTTE DEĞİL — kullanıcı istediği gibi yerleştirir."""

    visibilityChanged = pyqtSignal(bool)

    def __init__(self, scanner, parent=None):
        super().__init__(parent, Qt.Window)
        # Başlık oyun adını İÇERMEZ: aksi halde pencere arama bizim pencereye
        # kilitlenebilirdi (PID elemesi var ama isim de çakışmasın).
        self.setWindowTitle("Canlı Görünüm")
        self.setMinimumSize(320, 200)
        self.resize(760, 460)
        self._scanner = scanner
        self._shielded = False
        self._frame = None            # tamponu canlı tutar (QImage kopyalamaz)
        self._image = None
        self._stamp = None
        self._status = ""
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------ yaşam
    def start(self):
        if not self._timer.isActive():
            self._timer.start()
            self._tick()

    def stop(self):
        self._timer.stop()

    def set_status(self, text: str):
        """Pencere kayıp / yakalanamıyor gibi durumlar burada gösterilir."""
        if text != self._status:
            self._status = text or ""
            self.update()

    # ------------------------------------------------------------------ kare
    def _tick(self):
        frame, stamp, _origin = self._scanner.frame()
        if frame is None or stamp == self._stamp:
            return
        self._stamp = stamp
        # Tarayıcı yayınlanan kareyi DEĞİŞTİRMEZ, referansı değiştirir; bu
        # yüzden kopyalamadan gösterebiliriz. Referansı tutmak şart: QImage
        # tamponun sahibi değil.
        self._frame = frame
        height, width = frame.shape[:2]
        self._image = QImage(frame.data, width, height, width * 3,
                             QImage.Format_BGR888)
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), BACKGROUND)

        if self._image is not None:
            area = self.rect().adjusted(0, 0, 0, -18 if self._status else 0)
            scaled = self._image.scaled(area.width(), area.height(),
                                        Qt.KeepAspectRatio, Qt.FastTransformation)
            painter.drawImage(
                area.x() + (area.width() - scaled.width()) // 2,
                area.y() + (area.height() - scaled.height()) // 2,
                scaled,
            )
            if self._status:
                painter.fillRect(self.rect(), QColor(16, 18, 24, 140))
        if self._status:
            painter.setPen(TEXT_COLOR)
            painter.drawText(self.rect(), Qt.AlignCenter, self._status)
        elif self._image is None:
            painter.setPen(MUTED_COLOR)
            painter.drawText(self.rect(), Qt.AlignCenter,
                             "Görüntü bekleniyor…")

    # ------------------------------------------------------------------ olaylar
    def showEvent(self, event):
        super().showEvent(event)
        if not self._shielded:
            # Normal moda dönüldüğünde ekran yakalamayı kirletmesin.
            self._shielded = exclude_from_capture(self)

    def closeEvent(self, event):
        self.stop()
        self.visibilityChanged.emit(False)
        super().closeEvent(event)
