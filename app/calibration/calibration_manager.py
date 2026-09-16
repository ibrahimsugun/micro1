"""Kalibrasyon kayıtlarının merkezi.

Modüller buradan okur (kilitsiz: sözlük tek referans atamasıyla takas edilir),
Kalibrasyon sekmesi buraya yazar.
"""

from PyQt5.QtCore import QObject, pyqtSignal

from ..constants import CALIB_ORDER, CALIB_PARTY, PARTY_CALIB_ROWS
from .calibration_model import CalibrationRegion


class CalibrationManager(QObject):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._regions = {name: CalibrationRegion(name) for name in CALIB_ORDER}
        # Kayıt anındaki REFERANS: (origin_x, origin_y, genişlik, yükseklik).
        # origin = yakalanan karenin sol-üst köşesi (ekran modunda sanal
        # masaüstü köşesi, pencere modunda oyunun client köşesi). Çözünürlük /
        # zoom / oyun çözünürlüğü değişince rect'ler bu referansa göre ORANLA
        # yeniden hesaplanır (rescale_to).
        self.reference = None

    # ------------------------------------------------------------------ referans
    @property
    def screen_size(self):
        """Geriye uyum: referansın yalnız (genişlik, yükseklik) kısmı."""
        return (self.reference[2], self.reference[3]) if self.reference else None

    @screen_size.setter
    def screen_size(self, value):
        """Geriye uyum: yalnız boyut verilince origin korunur (yoksa 0,0)."""
        if not value:
            self.reference = None
            return
        ox, oy = (self.reference[0], self.reference[1]) if self.reference else (0, 0)
        self.reference = (ox, oy, int(value[0]), int(value[1]))

    def set_reference(self, origin, size):
        self.reference = (int(origin[0]), int(origin[1]),
                          int(size[0]), int(size[1]))

    def set_reference_from_scanner(self, scanner):
        """Yakalanan karenin origin + boyutunu referans olarak alır."""
        frame, _stamp, origin = scanner.frame()
        if frame is None:
            return False
        height, width = frame.shape[:2]
        if width <= 0 or height <= 0:
            return False
        self.set_reference(origin, (width, height))
        return True

    def rescale_to(self, origin, size) -> bool:
        """Tüm kayıtlı rect'leri REFERANStan yeni origin/boyuta oranlar.

        Konum client'a göre korunur, boyut orana göre büyür/küçülür. bar_geom
        kesirli (0-1) olduğu için dokunulmaz. Referans yoksa ya da fark yoksa
        hiçbir şey yapmaz.
        """
        if not self.reference:
            return False
        ox0, oy0, w0, h0 = self.reference
        nx0, ny0, nw, nh = int(origin[0]), int(origin[1]), int(size[0]), int(size[1])
        if w0 <= 0 or h0 <= 0 or nw <= 0 or nh <= 0:
            return False
        if (ox0, oy0, w0, h0) == (nx0, ny0, nw, nh):
            return False
        sx = nw / float(w0)
        sy = nh / float(h0)
        table = dict(self._regions)
        for name, region in table.items():
            if not region.saved or not region.rect:
                continue
            x, y, w, h = region.rect
            region.rect = (
                nx0 + int(round((x - ox0) * sx)),
                ny0 + int(round((y - oy0) * sy)),
                max(1, int(round(w * sx))),
                max(1, int(round(h * sy))),
            )
        self._regions = table
        self.reference = (nx0, ny0, nw, nh)
        self.changed.emit()
        return True

    def rescale_to_scanner(self, scanner) -> bool:
        """Şu anki yakalama boyutuna göre yeniden ölçekler."""
        frame, _stamp, origin = scanner.frame()
        if frame is None:
            return False
        height, width = frame.shape[:2]
        return self.rescale_to(origin, (width, height))

    # ------------------------------------------------------------------ okuma
    def get(self, name) -> CalibrationRegion:
        return self._regions.get(name) or CalibrationRegion(name)

    def rect(self, name):
        region = self._regions.get(name)
        return region.rect if region and region.saved else None

    def is_saved(self, name) -> bool:
        region = self._regions.get(name)
        return bool(region and region.saved)

    def saved_names(self):
        return [n for n in CALIB_ORDER if self.is_saved(n)]

    def unsaved_names(self):
        return [n for n in CALIB_ORDER if not self.is_saved(n)]

    def missing(self, names):
        return [n for n in names if not self.is_saved(n)]

    # ------------------------------------------------------------------ yazma
    def save_region(self, region: CalibrationRegion):
        region.saved = True
        table = dict(self._regions)
        table[region.name] = region
        self._regions = table
        self.changed.emit()

    def set_bar_geometry(self, name, geom):
        """Bir bölgenin bar geometrisini yerinde günceller.

        Eski profillerin otomatik geçişi için: kayıt yeniden yazılmaz, yalnız
        alan doldurulur. Okuyucular ya None ya da geometriyi görür; ikisi de
        geçerli yoldur, bu yüzden kilit gerekmez.
        """
        region = self._regions.get(name)
        if region is None or not region.saved:
            return False
        region.bar_geom = geom
        self.changed.emit()
        return True

    def delete_region(self, name):
        table = dict(self._regions)
        table[name] = CalibrationRegion(name)
        self._regions = table
        self.changed.emit()

    def clear(self):
        self._regions = {name: CalibrationRegion(name) for name in CALIB_ORDER}
        self.reference = None
        self.changed.emit()

    # ------------------------------------------------------------------ parti
    def party_row_height_exact(self) -> float:
        """Satır yüksekliği KESİRLİ tutulur (örn. %125 ölçekte 32.5).

        Tam sayıya kırpmak 8. satıra kadar birkaç piksel kayma biriktirir; bu
        da hem HP okumasını kaydırır hem de boş satırı üye gibi gösterir.
        """
        rect = self.rect(CALIB_PARTY)
        if not rect:
            return 0.0
        return max(1.0, rect[3] / float(PARTY_CALIB_ROWS))

    def party_row_height(self) -> int:
        """Gösterim için yuvarlanmış satır yüksekliği."""
        return int(round(self.party_row_height_exact()))

    def party_member_rect(self, index):
        """index. üyenin (0 tabanlı) satır dikdörtgeni.

        Satırlar kesirli yükseklikten türetilip birbirine EK YERİ BIRAKMADAN
        döşenir; böylece kayma birikmez.
        """
        rect = self.rect(CALIB_PARTY)
        if not rect:
            return None
        x, y, w, _h = rect
        row_h = self.party_row_height_exact()
        top = int(round(index * row_h))
        bottom = int(round((index + 1) * row_h))
        return (x, y + top, w, max(1, bottom - top))

    # ------------------------------------------------------------------ kalıcılık
    def to_dict(self) -> dict:
        data = {name: reg.to_dict() for name, reg in self._regions.items() if reg.saved}
        if self.reference:
            data["_ref"] = list(self.reference)
            data["_screen"] = [self.reference[2], self.reference[3]]  # eski uyum
        return data

    def load_dict(self, data):
        data = data or {}
        table = {}
        for name in CALIB_ORDER:
            payload = data.get(name)
            table[name] = (
                CalibrationRegion.from_dict(name, payload)
                if payload else CalibrationRegion(name)
            )
        self._regions = table
        ref = data.get("_ref")
        if ref and len(ref) == 4:
            self.reference = tuple(int(v) for v in ref)
        else:
            # Eski profil: yalnız (w, h) vardı; origin bilinmiyor → (0, 0).
            screen = data.get("_screen")
            self.reference = ((0, 0, int(screen[0]), int(screen[1]))
                              if screen else None)
        self.changed.emit()
