"""Sürüklenebilir / boyutlandırılabilir kalibrasyon çerçevesi.

Tasarım:
  * Üstte ince başlık şeridi: bölge adı + canlı okuma + Kaydet.
  * Ölçüm alanı 2 px renkli kenarlıkla çevrili; içi hafif tonlu.
  * Boyutlandırma köşe tutamağıyla değil, KENARLARDAN ve KÖŞELERDEN sürükleyerek
    yapılır (kenara 6 px yaklaşınca imleç değişir) — küçük tutamağı yakalamaya
    çalışmaktan çok daha kolay.

Pencere WDA_EXCLUDEFROMCAPTURE ile ekran yakalamadan çıkarıldığı için içindeki
ton ölçümü bozmaz; çıkarılamazsa iç alan tamamen saydama düşer.
"""

from PyQt5.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..constants import CALIB_COLORS, CALIB_LABELS
from ..services.capture_shield import exclude_from_capture

BORDER_PX = 2
BODY_TINT_ALPHA = 14     # iç tül: görünür kalsın ama altındaki barı gizlemesin
HEADER_H = 26
GRIP = 6                 # kenara bu kadar yaklaşınca boyutlandırma başlar
MIN_BODY_W = 24
MIN_BODY_H = 12

# Kenar/köşe -> imleç
_CURSORS = {
    (True, False, False, False): Qt.SizeHorCursor,    # sol
    (False, True, False, False): Qt.SizeHorCursor,    # sağ
    (False, False, True, False): Qt.SizeVerCursor,    # üst
    (False, False, False, True): Qt.SizeVerCursor,    # alt
    (True, False, True, False): Qt.SizeFDiagCursor,   # sol-üst
    (False, True, False, True): Qt.SizeFDiagCursor,   # sağ-alt
    (False, True, True, False): Qt.SizeBDiagCursor,   # sağ-üst
    (True, False, False, True): Qt.SizeBDiagCursor,   # sol-alt
}


class FrameWindow(QWidget):
    saveRequested = pyqtSignal(str)      # bölge adı
    closed = pyqtSignal(str)

    def __init__(self, name, initial_rect=None, parent=None):
        super().__init__(parent)
        self.name = name
        self.color = CALIB_COLORS.get(name, "#333333")
        self._drag_origin = None
        self._resize_edges = None
        self._resize_start = None
        self._shielded = False

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setWindowTitle(CALIB_LABELS.get(name, name))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- başlık şeridi -------------------------------------------------
        self.header = QWidget(self)
        self.header.setFixedHeight(HEADER_H)
        self.header.setMouseTracking(True)
        self.header.setStyleSheet(
            "background-color: {}; color: white;"
            "border-top-left-radius: 5px; border-top-right-radius: 5px;"
            .format(self.color)
        )
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(8, 0, 4, 0)
        header_layout.setSpacing(8)

        short = CALIB_LABELS.get(name, name).split(" (")[0]
        self.title_label = QLabel(short, self.header)
        self.title_label.setStyleSheet(
            "color: white; font-weight: 700; font-size: 11px; background: transparent;"
        )
        self.title_label.setToolTip(CALIB_LABELS.get(name, name))
        header_layout.addWidget(self.title_label)

        self.reading_label = QLabel("—", self.header)
        self.reading_label.setStyleSheet(
            "color: rgba(255,255,255,220); font-size: 11px; background: transparent;"
        )
        self.reading_label.setToolTip(
            "Çerçeve içindeki alandan şu an okunan değer. Kaydetmeden önce "
            "doğru okuduğundan emin ol."
        )
        header_layout.addWidget(self.reading_label)
        header_layout.addStretch(1)

        self.save_button = QPushButton("Kaydet", self.header)
        self.save_button.setFixedHeight(HEADER_H - 8)
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,235); color: #1e2430;"
            "border: none; border-radius: 4px; padding: 1px 10px;"
            "font-size: 11px; font-weight: 600; }"
            "QPushButton:hover { background: #ffffff; }"
        )
        self.save_button.setToolTip(
            "Bu çerçeveyi kaydeder: bölge, referans renk ve doluluk oranı "
            "örneklenir."
        )
        self.save_button.clicked.connect(lambda: self.saveRequested.emit(self.name))
        header_layout.addWidget(self.save_button)
        root.addWidget(self.header)

        # --- ölçüm alanı ---------------------------------------------------
        self.body = QFrame(self)
        self.body.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        tint = QColor(self.color)
        # Kenarlık KESİKLİ ve iç tül ince: çerçeve, altındaki barın hemen
        # dışındaki pikselleri kapatmasın — hizalama oraya bakılarak yapılıyor.
        # (Ölçümü etkilemez; pencere WDA_EXCLUDEFROMCAPTURE ile yakalamadan
        # çıkarılmış durumda.)
        self.body.setStyleSheet(
            "border: {}px dashed {};"
            "background-color: rgba({}, {}, {}, {});".format(
                BORDER_PX, self.color, tint.red(), tint.green(), tint.blue(),
                BODY_TINT_ALPHA,
            )
        )
        self.body.setMinimumSize(MIN_BODY_W, MIN_BODY_H)
        root.addWidget(self.body, 1)

        self.setMinimumSize(150, HEADER_H + MIN_BODY_H)
        if initial_rect:
            self.apply_body_rect(initial_rect)
        else:
            self.resize(210, HEADER_H + 30)

    # ------------------------------------------------------------------ ölçüm
    def _ratio(self) -> float:
        try:
            return float(self.devicePixelRatioF())
        except Exception:
            return 1.0

    def capture_rect(self):
        """Ölçülecek FİZİKSEL piksel dikdörtgeni (kenarlık dışarıda bırakılır)."""
        ratio = self._ratio()
        top_left = self.body.mapToGlobal(QPoint(BORDER_PX, BORDER_PX))
        width = max(1, self.body.width() - 2 * BORDER_PX)
        height = max(1, self.body.height() - 2 * BORDER_PX)
        return (
            int(round(top_left.x() * ratio)),
            int(round(top_left.y() * ratio)),
            int(round(width * ratio)),
            int(round(height * ratio)),
        )

    def apply_body_rect(self, rect):
        """Fiziksel piksel dikdörtgenini pencere geometrisine geri çevirir."""
        ratio = self._ratio() or 1.0
        x, y, w, h = (float(v) for v in rect)
        self.resize(
            max(150, int(round(w / ratio)) + 2 * BORDER_PX),
            HEADER_H + int(round(h / ratio)) + 2 * BORDER_PX,
        )
        self.move(
            int(round(x / ratio)) - BORDER_PX,
            int(round(y / ratio)) - BORDER_PX - HEADER_H,
        )

    def set_reading(self, text):
        self.reading_label.setText(text)

    # ------------------------------------------------------------------ olaylar
    def showEvent(self, event):
        super().showEvent(event)
        if not self._shielded:
            self._shielded = exclude_from_capture(self)
            if not self._shielded:
                # Yakalamadan gizlenemedi: iç tonu kaldır ki ölçüm bozulmasın.
                self.body.setStyleSheet(
                    "border: {}px dashed {}; background-color: rgba(0,0,0,0);"
                    .format(BORDER_PX, self.color)
                )

    def _edges_at(self, pos):
        """İmlecin hangi kenar/köşede olduğunu döndürür (sol, sağ, üst, alt)."""
        return (
            pos.x() <= GRIP,
            pos.x() >= self.width() - GRIP,
            pos.y() <= GRIP,
            pos.y() >= self.height() - GRIP,
        )

    def _update_cursor(self, pos):
        edges = self._edges_at(pos)
        cursor = _CURSORS.get(edges)
        self.setCursor(cursor if cursor else Qt.SizeAllCursor)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        edges = self._edges_at(event.pos())
        if any(edges):
            self._resize_edges = edges
            self._resize_start = (event.globalPos(), self.geometry())
        else:
            self._drag_origin = event.globalPos() - self.frameGeometry().topLeft()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._resize_edges and event.buttons() & Qt.LeftButton:
            self._resize_to(event.globalPos())
        elif self._drag_origin is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_origin)
        else:
            self._update_cursor(event.pos())
        event.accept()

    def _resize_to(self, global_pos):
        left, right, top, bottom = self._resize_edges
        start_pos, start_geo = self._resize_start
        delta = global_pos - start_pos
        geo = QRect(start_geo)
        if left:
            geo.setLeft(min(start_geo.left() + delta.x(),
                            start_geo.right() - self.minimumWidth()))
        if right:
            geo.setRight(max(start_geo.right() + delta.x(),
                             start_geo.left() + self.minimumWidth()))
        if top:
            geo.setTop(min(start_geo.top() + delta.y(),
                           start_geo.bottom() - self.minimumHeight()))
        if bottom:
            geo.setBottom(max(start_geo.bottom() + delta.y(),
                              start_geo.top() + self.minimumHeight()))
        self.setGeometry(geo)

    def mouseReleaseEvent(self, event):
        self._drag_origin = None
        self._resize_edges = None
        self._resize_start = None
        event.accept()

    def leaveEvent(self, event):
        self.unsetCursor()
        super().leaveEvent(event)

    def closeEvent(self, event):
        self.closed.emit(self.name)
        super().closeEvent(event)
