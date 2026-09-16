"""Kalibrasyon sekmesi: çerçeveleri yönetir, kayıtları listeler.

Tek düğme çerçeveleri açıp kapatır; kayıtlı olanlar da kaydedildikleri yer ve
boyutla gelir. Her çerçevenin kendi Kaydet düğmesi ve canlı okuma etiketi var.
"""

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...calibration.calibration_model import CalibrationRegion
from ...calibration.frame_window import FrameWindow
from ...constants import (
    CALIB_HP,
    CALIB_LABELS,
    CALIB_ORDER,
    CALIB_PARTY,
    CALIB_RPR,
    CALIB_TARGET,
    PARTY_CALIB_ROWS,
    RPR_BURNT_COLOR_BGR,
    RPR_TRIGGER_FRACTION,
)
from ...core import vision
from ..theme import CARD_SPACING, GREEN, MUTED, RED
from ..widgets.card import Card, hint_label


class CalibrationTab(QWidget):
    changed = pyqtSignal()

    def __init__(self, ctx, party_tracker, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.party = party_tracker
        self._frames = {}
        self._target_reminded = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(CARD_SPACING + 1)

        guide = Card("Nasıl", self)
        guide.add(hint_label(
            "Çerçeveleri oyundaki barların üzerine sürükle ve boyutlandır, "
            "sonra her çerçevenin Kaydet düğmesine bas.", guide,
        ))
        guide.add(hint_label(
            "• HP / MP barlarını TAM DOLUYKEN kaydet.\n"
            "• Hedef barı için önce bir mob seç.\n"
            "• Parti çerçevesi TAM 2 ÜYELİK alanı kapsamalı.\n"
            "• Silah alanını İKİ silah da YANIKKEN kaydet.", guide,
        ))
        self.toggle_button = QPushButton("Çerçeveleri göster", guide)
        self.toggle_button.setObjectName("primary")
        self.toggle_button.setToolTip(
            "Tüm çerçeveleri (kayıtlı olanlar dahil) ekrana getirir; tekrar "
            "basınca gizler. Gizlemek kayıtları silmez."
        )
        guide.add(self.toggle_button)

        self.rescan_button = QPushButton("Partiyi yeniden tara", guide)
        self.rescan_button.setToolTip(
            "Parti üye sayısını hemen yeniden sayar. Üye sayısı ayrıca 3 sn'de "
            "bir otomatik taranır."
        )
        guide.add(self.rescan_button)

        self.rescale_button = QPushButton("Çözünürlüğe göre yeniden ölçekle", guide)
        self.rescale_button.setToolTip(
            "Ekran çözünürlüğü, Windows ölçeği (zoom) ya da oyun çözünürlüğü "
            "değiştiyse, kayıtlı kalibrasyon dikdörtgenlerini yeni boyuta "
            "oranlar. Yeniden kalibrasyona gerek kalmadan hızlı bir düzeltmedir; "
            "sonuç tam oturmazsa ilgili bölgeyi elle yeniden kaydet."
        )
        guide.add(self.rescale_button)
        root.addWidget(guide)

        list_box = Card("Kayıtlar", self)
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(6)
        self.grid.setVerticalSpacing(6)
        self._rows = {}
        for row, name in enumerate(CALIB_ORDER):
            full = CALIB_LABELS[name]
            label = QLabel(full.split(" (")[0], list_box)
            label.setToolTip(full)
            summary = QLabel("kayıtlı değil", list_box)
            summary.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            summary.setWordWrap(True)
            summary.setStyleSheet("color: {}; font-size: 11px;".format(RED))
            delete = QPushButton("Sil", list_box)
            delete.setObjectName("ghost")
            delete.setFixedWidth(36)
            delete.setToolTip("Kaydı siler ve çerçeveyi geri getirir.")
            delete.clicked.connect(lambda _checked, n=name: self.delete_region(n))
            head = QHBoxLayout()
            head.setContentsMargins(0, 0, 0, 0)
            head.setSpacing(4)
            head.addWidget(label, 1)
            head.addWidget(delete)
            self.grid.addLayout(head, row * 2, 0)
            self.grid.addWidget(summary, row * 2 + 1, 0)
            self._rows[name] = (summary, delete)
        list_box.add_layout(self.grid)
        root.addWidget(list_box)
        root.addStretch(1)

        self.toggle_button.clicked.connect(self.toggle_frames)
        self.rescan_button.clicked.connect(self.party.request_rescan)
        self.rescale_button.clicked.connect(self._rescale_calibration)

        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._update_readings)
        self._timer.start()

        self.refresh_list()

    # ------------------------------------------------------------------ liste
    def refresh_list(self):
        for name in CALIB_ORDER:
            summary, delete = self._rows[name]
            region = self.ctx.calibration.get(name)
            if region.saved:
                # HP ailesi renkten bağımsız okunmak için bar geometrisi ister.
                # Eski profillerde bu bilgi yoktur; StatusReader onu canlı
                # ekrandan çıkarmayı dener, çıkaramazsa kullanıcı yeniden
                # kaydetmeli — aksi halde debuff renginde %0 okunmaya devam eder.
                needs_geom = (name in (CALIB_HP, CALIB_PARTY)
                              and region.bar_geom is None)
                summary.setText(
                    region.summary()
                    + (" · YENİDEN KAYDET (bar yeri çıkarılamadı)" if needs_geom else "")
                )
                summary.setStyleSheet(
                    "color: {}; font-size: 11px;".format(RED if needs_geom else GREEN)
                )
                delete.setEnabled(True)
            else:
                summary.setText("kayıtlı değil")
                summary.setStyleSheet("color: {}; font-size: 11px;".format(RED))
                delete.setEnabled(False)

    # ------------------------------------------------------------------ çerçeve
    def _rescale_calibration(self):
        """Kayıtlı kalibrasyonu şu anki yakalama boyutuna oranlar."""
        calib = self.ctx.calibration
        if not calib.reference or not calib.saved_names():
            QMessageBox.information(
                self, "Yeniden ölçekle",
                "Önce en az bir bölge kalibre edilmiş olmalı.",
            )
            return
        frame, _stamp, _origin = self.ctx.scanner.frame()
        if frame is None:
            QMessageBox.warning(
                self, "Yeniden ölçekle",
                "Şu an yakalanan bir kare yok. Oyun/pencere görünür olmalı.",
            )
            return
        old = calib.reference
        if not calib.rescale_to_scanner(self.ctx.scanner):
            QMessageBox.information(
                self, "Yeniden ölçekle",
                "Yakalama boyutu kayıt anıyla aynı; ölçekleme gerekmedi.",
            )
            return
        new = calib.reference
        if self._frames:                       # açık çerçeveleri yeni yere taşı
            self.hide_frames()
            self.show_frames()
        self.refresh_list()
        self.changed.emit()
        QMessageBox.information(
            self, "Yeniden ölçekle",
            "Kalibrasyon {}×{} → {}×{} olarak yeniden ölçeklendi.\n\n"
            "Kalıcı olması için Kaydet'e bas. Bir bölge tam oturmazsa onu "
            "Çerçeveleri göster ile elle düzeltebilirsin.".format(
                old[2], old[3], new[2], new[3]),
        )

    def toggle_frames(self):
        """Tek düğme: açık çerçeve varsa gizler, yoksa hepsini gösterir."""
        if self._frames:
            self.hide_frames()
        else:
            self.show_frames()

    def _refresh_toggle(self):
        self.toggle_button.setText(
            "Çerçeveleri gizle" if self._frames else "Çerçeveleri göster"
        )

    def show_frames(self, names=None):
        names = list(names) if names else list(CALIB_ORDER)
        for name in names:
            if name in self._frames:
                self._frames[name].raise_()
                continue
            region = self.ctx.calibration.get(name)
            frame = FrameWindow(name, region.rect if region.saved else None)
            frame.saveRequested.connect(self.save_region)
            frame.closed.connect(self._on_frame_closed)
            if not region.saved:
                self._place_default(frame, name)
            frame.show()
            self._frames[name] = frame
        self._refresh_toggle()
        if CALIB_TARGET in names and not self._target_reminded:
            self._target_reminded = True
            QMessageBox.information(
                self, "Hedef çerçevesi",
                "Hedef (mob) çerçevesini yerleştirmeden ÖNCE oyunda bir mob seç; "
                "aksi halde hedef barı ekranda görünmez.",
            )

    def _place_default(self, frame, name):
        offset = CALIB_ORDER.index(name) * 40
        frame.move(80 + offset, 80 + offset)
        if name == CALIB_PARTY:
            frame.resize(220, frame.height() + 30 * PARTY_CALIB_ROWS)
        elif name == CALIB_RPR:
            frame.resize(170, frame.height() + 40)

    def hide_frames(self):
        for frame in list(self._frames.values()):
            frame.close()
        self._frames.clear()
        self._refresh_toggle()

    def _on_frame_closed(self, name):
        self._frames.pop(name, None)
        self._refresh_toggle()

    # ------------------------------------------------------------------ kayıt
    def save_region(self, name):
        frame = self._frames.get(name)
        if frame is None:
            return
        rect = frame.capture_rect()
        image = self.ctx.scanner.region(rect)
        if image is None or image.size == 0:
            QMessageBox.warning(
                self, "Kalibrasyon",
                "Bu alandan görüntü alınamadı. Çerçeveyi ekran içine taşı.",
            )
            return

        region = CalibrationRegion(name, rect=rect)
        if name == CALIB_RPR:
            # Renk SABİT yanık kırmızısıdır (RPR_BURNT_COLOR_BGR); kayıt anında
            # örneklenmez. Silah tam yanınca hep bu renkte durduğu için en
            # güvenilir referans budur; kayıt anındaki dalgalı/soluk renk ya da
            # arka plandaki başka canlı renk yanlış referans veriyordu.
            ref = RPR_BURNT_COLOR_BGR
        else:
            # Doygun pikseller arasından örnekle: koyu zemin / çerçeve / yazı
            # baskın rengi ele geçirmesin. Parti barında hp_bar kayıtlıysa onun
            # tonuna yakın renk tercih edilir (KO'da parti HP barı da kırmızı).
            prefer = None
            if name == CALIB_PARTY:
                hp_region = self.ctx.calibration.get(CALIB_HP)
                if hp_region.saved and hp_region.ref_color:
                    prefer = vision.ref_hue(hp_region.ref_color)
            ref = vision.saturated_dominant_color(image, prefer_hue=prefer)
        if ref is None:
            QMessageBox.warning(self, "Kalibrasyon", "Referans renk örneklenemedi.")
            return
        region.ref_color = ref

        if name == CALIB_RPR:
            region.ratio_full = max(0.002, vision.color_presence_ratio(image, ref))
            if region.ratio_full < 0.01:
                QMessageBox.warning(
                    self, "Kalibrasyon",
                    "Bu alanda yanık silah rengi neredeyse hiç bulunamadı "
                    "(%{:.1f}).\n\nÇerçeveyi silahların üstüne al ve silahlar "
                    "YANIKKEN kaydet.".format(region.ratio_full * 100),
                )
                return
        else:
            region.ratio_full = max(0.01, vision.match_ratio(image, ref))

        # HP ailesi RENKTEN BAĞIMSIZ okunur: barın bölge içindeki yeri
        # çıkarılıp saklanır. Çıkarılamazsa kayıt reddedilir — yoksa kullanıcı
        # eski (renge bağlı) yolda kaldığını fark etmez.
        if name == CALIB_HP:
            geom = vision.detect_bar_geometry(image, ref)
            if geom is None:
                QMessageBox.warning(
                    self, "Kalibrasyon",
                    "Bu alanda bar bulunamadı.\n\nÇerçeveyi HP barının üstüne, "
                    "barın tamamını kapsayacak şekilde koy ve tekrar dene.",
                )
                return
            region.bar_geom = geom
        elif name == CALIB_PARTY:
            geom = self._party_geometry(image, region)
            if geom is None:
                return
            region.bar_geom = geom

        self.ctx.calibration.save_region(region)
        if not self.ctx.calibration.reference:
            self.ctx.calibration.set_reference_from_scanner(self.ctx.scanner)
        frame.close()
        self._frames.pop(name, None)
        self._refresh_toggle()
        self.refresh_list()
        self.changed.emit()

    def _party_geometry(self, image, region):
        """İlk 2 üyenin satırından bar geometrisini çıkarır ve DOĞRULAR.

        Satır yüksekliği seçilen alanın yarısıdır (mevcut tasarım). Geometri
        iki satır için AYRI AYRI çıkarılır; ikisi birbirini tutmuyorsa çerçeve
        tam 2 üyeyi kapsamıyor demektir ve kayıt reddedilir. Kullanıcı sonucu
        gözüyle doğrulasın diye iki üyenin okunan canı gösterilir.
        """
        height = image.shape[0]
        geoms, rows = [], []
        for index in range(PARTY_CALIB_ROWS):
            top = int(round(index * height / float(PARTY_CALIB_ROWS)))
            bottom = int(round((index + 1) * height / float(PARTY_CALIB_ROWS)))
            row = image[top:bottom]
            rows.append(row)
            # Üyelerden biri debuff yemişse ortak referans renk onun satırında
            # tutmaz; o yüzden satırın kendi rengiyle de bir kez denenir.
            geom = (vision.detect_bar_geometry(row, region.ref_color)
                    or vision.detect_bar_geometry(row, None))
            geoms.append(geom)

        if geoms[0] is None or geoms[1] is None:
            missing = 1 if geoms[0] is None else 2
            QMessageBox.warning(
                self, "Kalibrasyon",
                "{}. üyenin can barı bulunamadı.\n\nÇerçeve TAM 2 ÜYEYİ "
                "kapsamalı ve kayıt sırasında partide en az 2 kişi olmalı."
                .format(missing),
            )
            return None

        width = image.shape[1]
        left = abs(geoms[0].x0f - geoms[1].x0f) * width
        right = abs(geoms[0].x1f - geoms[1].x1f) * width
        if left > 3.0 or right > 3.0:
            QMessageBox.warning(
                self, "Kalibrasyon",
                "İki üyenin barı aynı yerde çıkmadı (sol {:.0f} px, sağ {:.0f} px "
                "fark).\n\nÇerçeve tam 2 üyeyi kapsamıyor olabilir; üst ve alt "
                "kenarı üyelerin satır sınırlarına hizala.".format(left, right),
            )
            return None

        geom = vision.BarGeometry(
            (geoms[0].x0f + geoms[1].x0f) / 2.0,
            (geoms[0].x1f + geoms[1].x1f) / 2.0,
            (geoms[0].y0f + geoms[1].y0f) / 2.0,
            (geoms[0].y1f + geoms[1].y1f) / 2.0,
        )
        percents = [vision.bar_percent_by_empty(row, geom) for row in rows]
        QMessageBox.information(
            self, "Kalibrasyon",
            "Parti barı kaydedildi.\n\nOkunan canlar:\n"
            "  1. üye: %{:.0f}\n  2. üye: %{:.0f}\n\n"
            "İkisi de tam canlıyken kaydettiysen bu değerler %97-100 arasında "
            "olmalı. Değilse çerçeveyi düzeltip tekrar kaydet."
            .format(percents[0], percents[1]),
        )
        return geom

    def delete_region(self, name):
        self.ctx.calibration.delete_region(name)
        self.refresh_list()
        self.show_frames([name])
        self.changed.emit()

    # ------------------------------------------------------------------ canlı
    def _update_readings(self):
        for name, frame in self._frames.items():
            rect = frame.capture_rect()
            image = self.ctx.scanner.region(rect)
            if image is None or image.size == 0:
                frame.set_reading("görüntü yok")
                continue
            if name == CALIB_RPR:
                saved = self.ctx.calibration.get(name)
                ref = (saved.ref_color if saved.saved and saved.ref_color
                       else vision.vivid_dominant_color(image))
                ratio = vision.color_presence_ratio(image, ref) if ref else 0.0
                if saved.saved and saved.ref_color:
                    trigger = saved.ratio_full * RPR_TRIGGER_FRACTION
                    frame.set_reading("yanık %{:.1f} · {}".format(
                        ratio * 100, "KIRIK" if ratio >= trigger else "sağlam"))
                else:
                    frame.set_reading("yanık %{:.1f}".format(ratio * 100))
                continue
            if name == CALIB_TARGET and vision.region_std(image) < 1.0:
                frame.set_reading("önce bir mob seç")
                continue
            saved = self.ctx.calibration.get(name)
            if saved.saved and saved.bar_geom is not None:
                # Kayıtlı geometri varsa gerçek ölçümün aynısı gösterilir.
                geom = saved.bar_geom
                if name == CALIB_PARTY:
                    # Parti kaydı 2 üyelik alan; okuma TEK satır üstünden.
                    image = image[:max(1, image.shape[0] // PARTY_CALIB_ROWS)]
                percent = vision.bar_percent_by_empty(image, geom)
            elif saved.saved and saved.ref_color:
                percent = vision.bar_percent(
                    image, saved.ref_color, ratio_full=saved.ratio_full
                )
            else:
                # Kayıttan önce ratio_full bilinmez; dolu kısım soldan başladığı
                # için referans rengi sol şeritten örnekleyip GENİŞLİK ölçüyoruz.
                strip = max(2, int(image.shape[1] * 0.15))
                ref = vision.saturated_dominant_color(image[:, :strip])
                percent = vision.fill_fraction_by_column(image, ref)
            frame.set_reading("şu an %{:.0f} okuyorum".format(percent))
