"""Oyunsuz test tezgahı: sahte bir Knight Online penceresi.

Ne yapar?
  * Başlığı ayarlanabilir (WindowGuard bu başlığı arar).
  * HP / MP / hedef barlarını kaydırıcılarla çiziyor.
  * 2-8 parti satırını aynı satır yüksekliğinde, bitişik çiziyor.
  * Sahte RPR ikonunu "kırık" / "sağlam" olarak çiziyor.
  * Aldığı TUŞLARI ve TIK koordinatlarını, aralarındaki süreyle listeler.

Kullanım:
    python birleşik/tools/dummy_game_window.py
"""

import random
import sys
import time


def _set_dpi_awareness():
    """Ana programla aynı fiziksel piksel uzayında olmak için şart."""
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


_set_dpi_awareness()

from PyQt5.QtCore import QEvent, QRect, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

DEFAULT_TITLE = "Dummy Knight Online"
MAX_MEMBERS = 8

BG = QColor(24, 24, 28)
EMPTY = QColor(45, 45, 50)
HP_COLOR = QColor(200, 30, 30)
# Gerçek oyunda yaratıkların atağına göre can barının RENGİ değişiyor. Tonlar
# tools/tests/ornekler altındaki gerçek ekran görüntülerinden ölçüldü
# (OpenCV ton ölçeği 0-180): normal 0, yanma 17.6, ice 38.4, mor 148.5.
DEBUFF_COLORS = [
    ("normal", QColor(200, 30, 30)),
    ("yanma", QColor(230, 110, 20)),
    ("ice / yavaşlatma", QColor(150, 235, 40)),
    ("mor (malice/zehir)", QColor(190, 60, 185)),
]
MP_COLOR = QColor(30, 90, 220)
TARGET_COLOR = QColor(210, 150, 20)
PARTY_COLOR = QColor(30, 175, 70)

HP_RECT = QRect(20, 20, 240, 22)
MP_RECT = QRect(20, 50, 240, 22)
TARGET_RECT = QRect(20, 92, 240, 18)
PARTY_ORIGIN = (20, 140)
PARTY_ROW_W = 200
PARTY_ROW_H = 34
# Silah alanı: karakterin iki elindeki silahlar. Yanık silah doygun kırmızı,
# sağlam silah çelik grisi. Arka plan HERHANGİ bir renk olabilir; tespitin
# yalnız kılıcın kendi rengine kilitlendiğini göstermek için değiştirilebilir.
RPR_RECT = QRect(236, 140, 96, 84)
# Gerçek yanık silah rengi (tools/tests/ornekler/rpr_yanik'ten ölçüldü):
# BGR(30,35,150) = RGB(150,35,30). Kod bu sabit renge göre tespit yapar.
BURNT_COLOR = QColor(150, 35, 30)
STEEL_COLOR = QColor(168, 172, 180)

TERRAIN_PRESETS = [
    ("Kahve arazi", QColor(78, 64, 52)),
    ("Yeşil çayır", QColor(52, 96, 44)),
    ("Mavi su", QColor(38, 66, 118)),
    ("Gri taş", QColor(96, 96, 100)),
    ("Kızıl-kahve toprak", QColor(112, 84, 78)),
    ("Kar", QColor(206, 210, 216)),
]


class GameCanvas(QWidget):
    """Sahte oyun ekranı — KO'ya benzetildi (gerçek oyun geri bildirimi):

    * Barlar dikey DEGRADE (üstte açık, altta koyu).
    * MP barının boşalan kısmı KOYU MAVİ kalır (siyah değil) — MP hatasını
      birebir tetikleyen senaryo.
    * Parti satırı = kırmızı HP barı + mavi MP barı + isim satırı.
    * Parti satırlarının DIŞI gürültülü desen (oyun dünyası taklidi) — std
      sapmayla varlık tespitinin patladığı senaryo.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(340, 420)
        # Can barının rengi (debuff taklidi). Ölçüm renkten bağımsız olmalı:
        # renk değişince okunan yüzde DEĞİŞMEMELİ.
        self.hp_color = HP_COLOR
        self.party_color = HP_COLOR
        self.hp = 100
        self.mp = 100
        self.target_visible = True
        self.target = 100
        self.member_count = 4
        self.members = [100] * MAX_MEMBERS
        self.left_burnt = False       # sol eldeki silah yanık mı
        self.right_burnt = False      # sağ eldeki silah yanık mı
        self.weapon_angle = 25        # kılıçların yönü (derece)
        self.terrain = TERRAIN_PRESETS[0][1]

    def member_rect(self, index) -> QRect:
        x, y = PARTY_ORIGIN
        return QRect(x, y + index * PARTY_ROW_H, PARTY_ROW_W, PARTY_ROW_H)

    def _draw_world(self, painter):
        """Oyun dünyası taklidi: deterministik, yüksek std'li karışık desen."""
        cell = 9
        for gy in range(0, self.height(), cell):
            for gx in range(0, self.width(), cell):
                seed = (gx * 73856093) ^ (gy * 19349663)
                r = 40 + (seed % 120)
                g = 50 + ((seed >> 7) % 130)
                b = 30 + ((seed >> 13) % 100)
                painter.fillRect(gx, gy, cell, cell, QColor(r, g, b))

    def paintEvent(self, _event):
        painter = QPainter(self)
        self._draw_world(painter)

        # Durum çubuğu zemini (kendi HP/MP/hedef barlarının arkası koyu panel)
        painter.fillRect(QRect(10, 10, 300, 110), BG)

        self._draw_bar(painter, HP_RECT, self.hp, self.hp_color, "HP",
                       empty=QColor(30, 8, 8))
        self._draw_bar(painter, MP_RECT, self.mp, MP_COLOR, "MP",
                       empty=QColor(8, 14, 42))   # koyu mavi boş kısım (KO)
        if self.target_visible:
            self._draw_bar(painter, TARGET_RECT, self.target, TARGET_COLOR,
                           "Hedef", empty=QColor(25, 20, 6))
        else:
            painter.fillRect(TARGET_RECT, BG)

        for index in range(MAX_MEMBERS):
            rect = self.member_rect(index)
            if index < self.member_count:
                self._draw_member(painter, rect, self.members[index], index)
            # üye olmayan satırlar: dünya deseni görünmeye devam eder

        self._draw_rpr(painter)

    def _draw_member(self, painter, rect, percent, index):
        """KO parti girişi: HP barı + MP barı + isim (koyu zemin üstünde)."""
        painter.fillRect(rect, QColor(16, 16, 20))
        painter.setPen(QPen(QColor(110, 110, 120), 1))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))

        bar_h = max(4, (rect.height() - 10) // 2)
        hp_rect = QRect(rect.x() + 3, rect.y() + 2, rect.width() - 6, bar_h)
        mp_rect = QRect(rect.x() + 3, rect.y() + 2 + bar_h + 1,
                        rect.width() - 6, bar_h)
        self._draw_bar(painter, hp_rect, percent, self.party_color, "",
                       empty=QColor(30, 8, 8))
        self._draw_bar(painter, mp_rect, 90, MP_COLOR, "",
                       empty=QColor(8, 14, 42))

        painter.setPen(QColor(235, 225, 180))
        painter.setFont(QFont("Segoe UI", 7))
        painter.drawText(
            QRect(rect.x() + 3, mp_rect.bottom() + 1,
                  rect.width() - 6, rect.bottom() - mp_rect.bottom() - 1),
            Qt.AlignVCenter, "Üye {}".format(index + 1),
        )

    def _draw_bar(self, painter, rect, percent, color, caption, empty=None):
        """Dikey degrade dolu kısım + (varsa) koyu renkli boş kısım."""
        painter.fillRect(rect, empty if empty is not None else EMPTY)
        fill_w = int((rect.width() - 2) * max(0, min(100, percent)) / 100.0)
        inner_h = rect.height() - 2
        for y in range(inner_h):
            bright = 1.0 - 0.5 * (y / max(1, inner_h))
            painter.fillRect(
                rect.x() + 1, rect.y() + 1 + y, fill_w, 1,
                QColor(int(color.red() * bright), int(color.green() * bright),
                       int(color.blue() * bright)),
            )
        if caption:
            painter.setPen(QColor(230, 230, 230))
            painter.setFont(QFont("Segoe UI", 7))
            painter.drawText(rect.adjusted(4, 0, 0, 0), Qt.AlignVCenter, caption)

    def _draw_rpr(self, painter):
        """Silah alanı: gürültülü arazi zemini + iki kılıç.

        Kılıçlar açıyla döndürülerek çizilir; tespit RENGE baktığı için yön
        sonucu değiştirmemelidir (testler bunu doğruluyor).
        """
        # Arazi taklidi: seçili zemin renginin çevresinde gürültü.
        rng = random.Random(7)          # her karede aynı desen (kararlı test)
        base = self.terrain
        for y in range(RPR_RECT.top(), RPR_RECT.bottom() + 1, 3):
            for x in range(RPR_RECT.left(), RPR_RECT.right() + 1, 3):
                jitter = rng.randint(-22, 22)
                painter.fillRect(x, y, 3, 3, QColor(
                    max(0, min(255, base.red() + jitter)),
                    max(0, min(255, base.green() + jitter)),
                    max(0, min(255, base.blue() + jitter)),
                ))

        # Oyunda kılıçlar çapraz YUKARI bakar: solda sola, sağda sağa.
        half = RPR_RECT.width() // 2
        self._draw_sword(
            painter,
            RPR_RECT.left() + half // 2, RPR_RECT.center().y(),
            -self.weapon_angle,
            BURNT_COLOR if self.left_burnt else STEEL_COLOR,
            mirror=True,
        )
        self._draw_sword(
            painter,
            RPR_RECT.left() + half + half // 2, RPR_RECT.center().y(),
            self.weapon_angle,
            BURNT_COLOR if self.right_burnt else STEEL_COLOR,
        )

    @staticmethod
    def _draw_sword(painter, cx, cy, angle, color, mirror=False):
        """KAVİSLİ pala: oyundaki gibi çapraz yukarı bakar.

        Tespit yalnız RENGE baktığı için bu şeklin ayrıntısı sonucu
        değiştirmez; tezgâhın gerçeğe benzemesi ve testin gerçekçi bir
        siluetle sınanması için böyle çizilir.
        """
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(angle)
        if mirror:
            painter.scale(-1, 1)

        blade = QPainterPath()
        blade.moveTo(-3.0, 16.0)                  # sırt, kabza hizası
        blade.quadTo(-11.0, -6.0, -6.0, -30.0)    # dışa doğru kavis
        blade.lineTo(-1.0, -33.0)                 # uç
        blade.quadTo(2.0, -30.0, 2.5, -26.0)      # ucun iç kenarı
        blade.quadTo(4.0, -2.0, 3.0, 16.0)        # keskin yüz geri iner
        blade.closeSubpath()
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawPath(blade)

        painter.fillRect(-9, 14, 18, 4, color)    # balçak
        painter.fillRect(-2, 18, 4, 10, color)    # sap
        painter.restore()


class DummyGameWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(DEFAULT_TITLE)
        self.resize(760, 560)
        self._last_event = None

        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        left = QVBoxLayout()
        self.canvas = GameCanvas(self)
        left.addWidget(self.canvas, 1)

        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("Pencere başlığı:", self))
        self.title_edit = QLineEdit(DEFAULT_TITLE, self)
        title_row.addWidget(self.title_edit, 1)
        apply_button = QPushButton("Uygula", self)
        apply_button.clicked.connect(
            lambda: self.setWindowTitle(self.title_edit.text() or DEFAULT_TITLE)
        )
        title_row.addWidget(apply_button)
        left.addLayout(title_row)
        root.addLayout(left, 1)

        right = QVBoxLayout()
        right.addWidget(self._build_controls())

        log_box = QGroupBox("Alınan tuşlar ve tıklar", self)
        log_layout = QVBoxLayout(log_box)
        self.log = QListWidget(log_box)
        self.log.setFocusPolicy(Qt.NoFocus)
        log_layout.addWidget(self.log)
        clear_button = QPushButton("Listeyi temizle", log_box)
        clear_button.clicked.connect(self.log.clear)
        log_layout.addWidget(clear_button)
        right.addWidget(log_box, 1)
        root.addLayout(right, 1)

        self.setFocusPolicy(Qt.StrongFocus)
        self._last_seen = (None, 0.0)
        QApplication.instance().installEventFilter(self)

    # ------------------------------------------------------------------ kontrol
    def _build_controls(self):
        box = QGroupBox("Sahte oyun durumu", self)
        grid = QGridLayout(box)
        grid.setVerticalSpacing(3)

        self.hp_slider = self._slider(grid, 0, "HP", 100, self._on_hp)
        self.mp_slider = self._slider(grid, 1, "MP", 100, self._on_mp)
        self.target_slider = self._slider(grid, 2, "Hedef", 100, self._on_target)

        self.target_check = QCheckBox("Hedef seçili", box)
        self.target_check.setChecked(True)
        self.target_check.toggled.connect(self._on_target_visible)
        grid.addWidget(self.target_check, 3, 0, 1, 3)

        grid.addWidget(QLabel("Parti üye sayısı:", box), 4, 0)
        self.count_spin = QSpinBox(box)
        self.count_spin.setRange(0, MAX_MEMBERS)
        self.count_spin.setValue(4)
        self.count_spin.valueChanged.connect(self._on_count)
        grid.addWidget(self.count_spin, 4, 1, 1, 2)

        self.member_sliders = []
        for i in range(MAX_MEMBERS):
            slider = self._slider(grid, 5 + i, "Üye {}".format(i + 1), 100,
                                  lambda value, index=i: self._on_member(index, value))
            self.member_sliders.append(slider)

        row = 5 + MAX_MEMBERS
        self.left_burnt_check = QCheckBox("Sol silah yanık", box)
        self.left_burnt_check.toggled.connect(self._on_left_burnt)
        grid.addWidget(self.left_burnt_check, row, 0, 1, 3)
        self.right_burnt_check = QCheckBox("Sağ silah yanık", box)
        self.right_burnt_check.toggled.connect(self._on_right_burnt)
        grid.addWidget(self.right_burnt_check, row + 1, 0, 1, 3)
        self.angle_slider = self._slider(
            grid, row + 2, "Kılıç yönü", 25, self._on_angle, maximum=180
        )
        grid.addWidget(QLabel("HP bar rengi:", box), row + 4, 0)
        self.hp_color_combo = QComboBox(box)
        for label, color in DEBUFF_COLORS:
            self.hp_color_combo.addItem(label, color)
        self.hp_color_combo.currentIndexChanged.connect(self._on_hp_color)
        grid.addWidget(self.hp_color_combo, row + 4, 1, 1, 2)

        grid.addWidget(QLabel("Parti bar rengi:", box), row + 5, 0)
        self.party_color_combo = QComboBox(box)
        for label, color in DEBUFF_COLORS:
            self.party_color_combo.addItem(label, color)
        self.party_color_combo.currentIndexChanged.connect(self._on_party_color)
        grid.addWidget(self.party_color_combo, row + 5, 1, 1, 2)

        grid.addWidget(QLabel("Zemin:", box), row + 3, 0)
        self.terrain_combo = QComboBox(box)
        for caption, _color in TERRAIN_PRESETS:
            self.terrain_combo.addItem(caption)
        self.terrain_combo.currentIndexChanged.connect(self._on_terrain)
        grid.addWidget(self.terrain_combo, row + 3, 1, 1, 2)
        return box

    def _slider(self, grid, row, caption, value, handler, maximum=100):
        box = grid.parentWidget()
        grid.addWidget(QLabel(caption, box), row, 0)
        slider = QSlider(Qt.Horizontal, box)
        slider.setRange(0, maximum)
        slider.setValue(value)
        label = QLabel("%{}".format(value), box)
        label.setMinimumWidth(34)

        def on_change(new_value):
            label.setText("%{}".format(new_value))
            handler(new_value)

        slider.valueChanged.connect(on_change)
        grid.addWidget(slider, row, 1)
        grid.addWidget(label, row, 2)
        return slider

    def _on_hp_color(self, index):
        self.canvas.hp_color = self.hp_color_combo.itemData(index)
        self.canvas.update()

    def _on_party_color(self, index):
        self.canvas.party_color = self.party_color_combo.itemData(index)
        self.canvas.update()

    def _on_hp(self, value):
        self.canvas.hp = value
        self.canvas.update()

    def _on_mp(self, value):
        self.canvas.mp = value
        self.canvas.update()

    def _on_target(self, value):
        self.canvas.target = value
        self.canvas.update()

    def _on_target_visible(self, value):
        self.canvas.target_visible = bool(value)
        self.canvas.update()

    def _on_count(self, value):
        self.canvas.member_count = value
        self.canvas.update()

    def _on_member(self, index, value):
        self.canvas.members[index] = value
        self.canvas.update()

    def _on_left_burnt(self, value):
        self.canvas.left_burnt = bool(value)
        self.canvas.update()

    def _on_right_burnt(self, value):
        self.canvas.right_burnt = bool(value)
        self.canvas.update()

    def _on_angle(self, value):
        self.canvas.weapon_angle = value
        self.canvas.update()

    def _on_terrain(self, index):
        self.canvas.terrain = TERRAIN_PRESETS[index][1]
        self.canvas.update()

    # ------------------------------------------------------------------ kayit
    def _log(self, text):
        now = time.monotonic()
        delta = "" if self._last_event is None else "  (+{} ms)".format(
            int((now - self._last_event) * 1000)
        )
        self._last_event = now
        self.log.addItem(time.strftime("%H:%M:%S") + "  " + text + delta)
        self.log.scrollToBottom()
        if self.log.count() > 500:
            self.log.takeItem(0)

    @staticmethod
    def _key_name(event) -> str:
        """F1-F15 gibi metinsiz tuşları da okunur biçimde adlandırır."""
        code = event.key()
        if Qt.Key_F1 <= code <= Qt.Key_F35:
            return "F{}".format(code - Qt.Key_F1 + 1)
        named = {
            Qt.Key_Space: "BOŞLUK", Qt.Key_Return: "ENTER", Qt.Key_Enter: "ENTER",
            Qt.Key_Escape: "ESC", Qt.Key_Tab: "TAB", Qt.Key_Backspace: "GERİ SİL",
            Qt.Key_Delete: "DELETE", Qt.Key_Home: "HOME", Qt.Key_End: "END",
            Qt.Key_Up: "YUKARI OK", Qt.Key_Down: "AŞAĞI OK",
            Qt.Key_Left: "SOL OK", Qt.Key_Right: "SAĞ OK",
        }
        if code in named:
            return named[code]
        text = event.text().upper().strip()
        return text if text else "kod {}".format(code)

    def _is_duplicate(self, token) -> bool:
        """Ayni olay ust widget'lara yayilirken iki kez yazilmasin."""
        now = time.monotonic()
        last_token, last_time = self._last_seen
        if token == last_token and (now - last_time) < 0.02:
            return True
        self._last_seen = (token, now)
        return False

    def eventFilter(self, obj, event):
        """Odak hangi widget'ta olursa olsun tus ve tiklari kaydet."""
        kind = event.type()
        if kind not in (QEvent.KeyPress, QEvent.MouseButtonPress):
            return False
        try:
            if obj.window() is not self:
                return False
        except AttributeError:
            return False

        if kind == QEvent.KeyPress:
            if event.isAutoRepeat():
                return False
            name = self._key_name(event)
            if not self._is_duplicate(("key", name)):
                self._log("TUŞ: {}".format(name))
            return False

        point = self.canvas.mapFromGlobal(event.globalPos())
        hit = ""
        for index in range(self.canvas.member_count):
            if self.canvas.member_rect(index).contains(point):
                hit = "  -> Parti üyesi {}".format(index + 1)
                break
        token = ("click", event.globalX(), event.globalY())
        if not self._is_duplicate(token):
            self._log("TIK: ekran ({}, {}){}".format(
                event.globalX(), event.globalY(), hit
            ))
        return False


def main():
    app = QApplication(sys.argv)
    window = DummyGameWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
