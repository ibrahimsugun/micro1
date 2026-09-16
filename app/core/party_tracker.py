"""Parti üyelerinin satırlarını türetir ve HP oranlarını okur.

party_bar kaydı TAM 2 üyelik alanı kapsar; satır yüksekliği bu kayıttan
türetilir ve en fazla 8 üyeye kadar aşağı doğru uzatılır.

Üye SAYISI tercihen elle verilir (set_manual_count). Otomatik sayım bu işin en
zor görüntü problemi — boş satırın arkası oyun dünyasıdır — ve sayıyı kullanıcı
zaten biliyor; elle verilince sayım maliyeti de hata riski de sıfırlanır.
Solo seçilirse parti hiç okunmaz.

HP yüzdesi, kayıtlı bar geometrisi varsa RENKTEN BAĞIMSIZ okunur: yalnız
üyenin HP bandındaki boş sütunlar sayılır, MP barına hiç girilmez.
"""

import threading
import time

from ..constants import (
    CALIB_PARTY,
    MAX_PARTY_MEMBERS,
    PARTY_RESCAN_MS,
)
from . import vision


class PartyTracker:
    """Thread güvenli; hem heal modülü hem de UI okuyucusu çağırabilir."""

    def __init__(self, scanner, calibration):
        self._scanner = scanner
        self._calib = calibration
        self._lock = threading.Lock()
        self._members = []
        self._count = 0
        self._last_stamp = None
        self._last_scan = 0.0
        self._force_scan = True
        self._manual_count = None      # None = otomatik say, 0 = solo, 1-8 = sabit

    # ------------------------------------------------------------------ arayüz
    def request_rescan(self):
        """'Partiyi Yeniden Tara' butonu (yalnız otomatik sayımda anlamlı)."""
        with self._lock:
            self._force_scan = True
            self._last_stamp = None      # kare önbelleğini geçersiz kıl

    def set_manual_count(self, count):
        """None = otomatik say, 0 = solo (parti hiç okunmaz), 1-8 = sabit sayı."""
        with self._lock:
            self._manual_count = None if count is None else max(0, int(count))
            self._force_scan = True
            # Kare değişmeden ayar değişti; önbellek geçersiz kılınmazsa eski
            # üye listesi dönerdi (solo seçilince parti kaybolmazdı).
            self._last_stamp = None

    def manual_count(self):
        with self._lock:
            return self._manual_count

    def member_count(self) -> int:
        with self._lock:
            return self._count

    def members(self):
        with self._lock:
            return list(self._members)

    def update(self, force=False):
        """Satırları okur; KARE BAŞINA en fazla bir kez gerçek iş yapar.

        Zaman freni yerine tarayıcı kare damgası kullanılır: kare değişmeden
        yeniden okumak birebir aynı sonucu verir. Heal modülü 10 Hz,
        StatusReader 3.3 Hz çağırıyor; ikisi de aynı kareyi işliyordu.
        """
        now = time.monotonic()
        stamp = self._scanner.stamp()
        with self._lock:
            if not force and stamp == self._last_stamp:
                return list(self._members)
            rescan = self._force_scan or (now - self._last_scan) * 1000.0 >= PARTY_RESCAN_MS
            manual = self._manual_count

        region = self._calib.get(CALIB_PARTY)
        if not region.saved or not region.rect or manual == 0:
            # Solo: hiçbir satır okunmaz, parti maliyeti sıfır.
            with self._lock:
                self._members, self._last_stamp = [], stamp
                if manual == 0:
                    self._count = 0
            return []

        ref = region.ref_color
        ratio_full = region.ratio_full
        geom = region.bar_geom
        limit = MAX_PARTY_MEMBERS if manual is None else min(manual, MAX_PARTY_MEMBERS)

        members = []
        for i in range(limit):
            # Satır dikdörtgenini kalibrasyon yöneticisi kesirli yükseklikten
            # türetir; burada tam sayı çarpımı YAPILMAZ (kayma birikmesin).
            row_rect = self._calib.party_member_rect(i)
            if row_rect is None:
                break
            rx, ry, rw, rh = row_rect
            center = (rx + rw // 2, ry + rh // 2)
            img = self._scanner.region(row_rect)
            if img is None:
                members.append({
                    "index": i, "present": False, "percent": 0.0,
                    "center": center, "rect": row_rect, "state": None,
                })
                continue
            if manual is not None:
                # Sayı elle verildi: bu satır tanım gereği üyedir. Varlık
                # testi hiç çalışmaz -> satır başına iki HSV geçişi düşer.
                present = True
            elif geom is not None:
                present = vision.band_row_present(img, geom)
            else:
                # Geometri yoksa eski yol (kayıtlı kırmızı tonu + karanlık).
                present = vision.party_row_present(img, ref)

            if not present:
                percent, state = 0.0, None
            elif geom is not None:
                percent = vision.bar_percent_by_empty(img, geom)
                state = vision.bar_state(img, geom)
            else:
                percent = vision.bar_percent(img, ref, ratio_full=ratio_full)
                state = None
            members.append({
                "index": i,
                "present": present,
                "percent": percent,
                "center": center,
                "rect": row_rect,
                "state": state,
            })

        with self._lock:
            if manual is not None:
                self._count = len(members)
            elif rescan:
                count = 0
                for m in members:
                    if not m["present"]:
                        break
                    count += 1
                self._count = count
                self._last_scan = now
                self._force_scan = False
            count = self._count
            # Üye sayısı dışındaki satırlar listelenmez.
            self._members = members[:count]
            self._last_stamp = stamp
            return list(self._members)

    # ------------------------------------------------------------------ seçim
    def lowest_below(self, threshold):
        """Eşik altındaki en düşük HP'li üye (yoksa None)."""
        candidates = [m for m in self.members() if m["present"] and m["percent"] < threshold]
        if not candidates:
            return None
        return min(candidates, key=lambda m: m["percent"])

    def count_below(self, threshold) -> int:
        return sum(1 for m in self.members() if m["present"] and m["percent"] < threshold)
