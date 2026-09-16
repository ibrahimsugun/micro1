"""Canlı değerleri okuyup LiveStatus'a yazan GUI zamanlayıcısı.

Modüller kendi kararları için ekranı doğrudan okur; burası yalnız Bilgi sekmesi,
overlay, ölüm koruması ve kalibrasyon canlı okuması için ortak kaynaktır.
QTimer olduğu için yalnız GUI thread'inde çalışır (kural #5).
"""

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from ..constants import (
    CALIB_HP,
    CALIB_MP,
    CALIB_PARTY,
    CALIB_RPR,
    CALIB_TARGET,
    HP_STATE_LABELS,
    HP_STATE_UNKNOWN,
    TARGET_PRESENT_RATIO,
)
from . import vision

# Eski profilin geometrisi bu kadar denemede çıkarılamazsa vazgeçilir
# (ilk karelerde ekran hazır olmayabilir; 20 tur ~6 saniye).
GEOMETRY_ATTEMPTS = 20


class StatusReader(QObject):
    resolutionMismatch = pyqtSignal(tuple, tuple)   # (kayıtlı, şimdiki)

    def __init__(self, ctx, party_tracker, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.party = party_tracker
        self._warned_resolution = False
        # Eski profiller için bar geometrisi çıkarma denemeleri (bölge -> kalan)
        self._geometry_left = {CALIB_HP: GEOMETRY_ATTEMPTS,
                               CALIB_PARTY: GEOMETRY_ATTEMPTS}
        self._timer = QTimer(self)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self.refresh)

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    # ------------------------------------------------------------------ okuma
    def read_percent(self, name):
        """(yüzde, bar görünür mü) — kayıt yoksa (None, False).

        Ölçümü ModuleContext yapar: hem kod tekrarı olmaz hem de kare damgalı
        önbellekten yararlanılır (modüller aynı kareyi zaten okuduysa yeniden
        hesaplanmaz).
        """
        region = self.ctx.calibration.get(name)
        if not region.saved or not region.rect:
            return None, False
        img = self.ctx.scanner.region(region.rect)
        if img is None:
            return None, False
        present = vision.region_std(img) > 0.5
        return self.ctx.bar_percent(name), present

    def _ensure_geometry(self):
        """Eski profillerde bar geometrisini canlı ekrandan bir kez çıkarır.

        Renkten bağımsız okuma barın bölge içindeki YERİNİ bilmek zorunda;
        eski kayıtlarda bu alan yok. Çıkarılabilirse profile yazılır ve okuma
        kendiliğinden yeni yola geçer; çıkarılamazsa eski tümevarım yolunda
        kalınır ve Kalibrasyon sekmesi "yeniden kaydet" uyarısı gösterir.
        """
        for name in list(self._geometry_left):
            region = self.ctx.calibration.get(name)
            if not region.saved or region.bar_geom is not None:
                self._geometry_left.pop(name, None)
                continue
            # Parti kaydı 2 üyelik alandır; geometri TEK satırdan çıkarılır.
            rect = (self.ctx.calibration.party_member_rect(0)
                    if name == CALIB_PARTY else region.rect)
            img = self.ctx.scanner.region(rect) if rect else None
            geom = vision.detect_bar_geometry(img, region.ref_color) if img is not None else None
            if geom is not None:
                self.ctx.calibration.set_bar_geometry(name, geom)
                self._geometry_left.pop(name, None)
                continue
            self._geometry_left[name] -= 1
            if self._geometry_left[name] <= 0:
                self._geometry_left.pop(name, None)

    def read_state(self):
        """(durum anahtarı, etiket) — geometri yoksa (None, "")."""
        key = self.ctx.bar_state(CALIB_HP)
        if key is None:
            geom = self.ctx.calibration.get(CALIB_HP).bar_geom
            if geom is None:
                return None, ""
            return HP_STATE_UNKNOWN, "bilinmeyen durum"
        return key, HP_STATE_LABELS.get(key, key)

    def read_rpr(self):
        return self.ctx.rpr_broken()

    def refresh(self):
        live = self.ctx.live
        self._ensure_geometry()
        hp, hp_present = self.read_percent(CALIB_HP)
        hp_state, hp_state_label = self.read_state()
        mp, _mp_present = self.read_percent(CALIB_MP)
        target_percent, _tp = self.read_percent(CALIB_TARGET)
        target_on = (target_percent or 0.0) > TARGET_PRESENT_RATIO

        members = self.party.update()
        live.update(
            hp_percent=hp,
            hp_present=hp_present,
            hp_state=hp_state,
            hp_state_label=hp_state_label,
            mp_percent=mp,
            target_percent=target_percent or 0.0,
            target_present=target_on,
            rpr_broken=self.read_rpr(),
            rpr_ratio=self.ctx.rpr_ratio(),
            party=members,
            party_count=len(members),
            input_backend=self.ctx.input.backend,
            scanner_fps=round(self.ctx.scanner.fps, 1),
        )
        self._check_resolution()

    def _check_resolution(self):
        from ..services.screen_scanner import MODE_WINDOW

        if self.ctx.scanner.mode() == MODE_WINDOW:
            self._check_window_bounds()
            return

        saved = self.ctx.calibration.screen_size
        if not saved:
            return
        current = self.ctx.scanner.screen_size()
        if current == (0, 0):
            return
        if tuple(saved) == tuple(current):
            if not self.ctx.state.resolution_ok.is_set():
                self.ctx.state.resolution_ok.set()
                self._warned_resolution = False
            return
        self._fail_resolution(tuple(saved), tuple(current))

    def _check_window_bounds(self):
        """Arka plan modu: kare EKRANIN tamamı değil, pencerenin client alanı.

        Bu yüzden kayıtlı ekran çözünürlüğüyle karşılaştırmak anlamsızdır.
        Doğru soru şudur: kalibre edilmiş dikdörtgenler yakalanan karenin
        İÇİNDE mi? Değilse (pencere taşınmış/boyutlanmış) ölçüm sessizce
        yanlış okurdu — hatta bar hiç görünmeyip sahte ölüm alarmı verirdi.
        """
        frame, _stamp, origin = self.ctx.scanner.frame()
        if frame is None:
            return
        height, width = frame.shape[:2]
        rects = [self.ctx.calibration.rect(name)
                 for name in self.ctx.calibration.saved_names()]
        rects = [r for r in rects if r]
        if not rects:
            if not self.ctx.state.resolution_ok.is_set():
                self.ctx.state.resolution_ok.set()
                self._warned_resolution = False
            return

        saved = self.ctx.calibration.screen_size or (width, height)
        for x, y, w, h in rects:
            left = x - origin[0]
            top = y - origin[1]
            if left < 0 or top < 0 or left + w > width or top + h > height:
                # Pencere taşınmış/boyutlanmış: kalibre bölge kare dışına çıktı.
                self._fail_resolution(tuple(saved), (width, height))
                return

        if not self.ctx.state.resolution_ok.is_set():
            self.ctx.state.resolution_ok.set()
            self._warned_resolution = False

    def _fail_resolution(self, saved, current):
        self.ctx.state.resolution_ok.clear()
        if not self._warned_resolution:
            self._warned_resolution = True
            self.resolutionMismatch.emit(tuple(saved), tuple(current))
