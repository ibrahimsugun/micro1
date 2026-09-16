"""Gerçek oyun ekran görüntüleriyle renkten bağımsız can okuması.

Diğer testler canlı ekrandan okur; bu test ÇEVRİMDIŞIDIR çünkü elimizde
oyunun kendi pikselleri var (tools/tests/ornekler/). Sentetik bir bar hiçbir
zaman gerçek barın degradesini, can yazısının siyah konturunu ve çerçevenin
açık gri çizgisini birebir taklit edemez.

Ölçülen gerçekler (bu testin dayandığı zemin):
  * Barın BOŞ kısmı, dolu kısmın rengi ne olursa olsun siyah kalıyor
    (dolu bölge V = 86..167, boş bölge V = 0..45).
  * malice.png'de can 3781/3781, yani TAM DOLU, ama bar MOR. Eski yöntem
    burada %0 okuyup "öldük" alarmı veriyordu; düzeltmenin sebebi bu.
  * yanma.png'de bar ile yazan sayı UYUŞMUYOR (bar %83, yazı %74.5): yanarken
    can sürekli tükendiği için bar animasyonu sayıya yetişemiyor. Bu yüzden
    doğruluk kontrolü yazıya değil, barın kendi piksellerine göre yapılır.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

from app.core import vision  # noqa: E402

try:
    import cv2
    CV2_AVAILABLE = True
except Exception:                                    # pragma: no cover
    CV2_AVAILABLE = False

ORNEKLER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ornekler")

# (dosya, kullanıcının çizeceği çerçeve (x0, y0, x1, y1), beklenen renk durumu,
#  beklenen doluluk — barın kendi piksellerinden ölçülmüş, None = kontrol yok)
CASES = [
    ("normal.png", (4, 34, 254, 56), "normal", 100.0),
    ("zehir.png", (38, 37, 296, 58), "mor", 48.1),
    ("yanma.png", (5, 12, 285, 33), "yanma", 83.0),
    ("malice.png", (19, 33, 210, 54), "mor", 100.0),
]
PARTY_FILE = "örnek party'de herkesin üzerinde debuff var.png"
PARTY_RECT = (0, 0, 62, 80)              # kullanıcı İLK 2 ÜYEyi seçer
PARTY_EXPECTED = [100.0, 91.9, 100.0, 59.7, 58.1, 100.0]
TOLERANCE = 4.0                          # puan

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("[{}] {}{}".format("PASS" if ok else "FAIL", name,
                             ("  -- " + detail) if detail else ""))


def load(fname):
    """PNG -> BGR dizi. Türkçe karakterli dosya adları için imdecode kullanılır
    (cv2.imread yolu ANSI'ye çevirmeye çalışıp başarısız oluyor)."""
    path = os.path.join(ORNEKLER, fname)
    with open(path, "rb") as handle:
        buf = np.frombuffer(handle.read(), dtype=np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def crop(img, rect):
    x0, y0, x1, y1 = rect
    return np.ascontiguousarray(img[y0:y1, x0:x1])


def main():
    if not CV2_AVAILABLE:
        print("opencv yok, test atlaniyor")
        return 0
    if not os.path.isdir(ORNEKLER):
        print("ornekler klasoru yok, test atlaniyor")
        return 0

    for fname, rect, expected_state, expected_percent in CASES:
        if not os.path.exists(os.path.join(ORNEKLER, fname)):
            print("  {} yok, atlaniyor".format(fname))
            continue
        img = crop(load(fname), rect)
        ref = vision.saturated_dominant_color(img)
        geom = vision.detect_bar_geometry(img, ref)
        check("{}: bar geometrisi çıkarıldı".format(fname), geom is not None)
        if geom is None:
            continue

        percent = vision.bar_percent_by_empty(img, geom)
        check("{}: can %{:.0f} okundu".format(fname, expected_percent),
              abs(percent - expected_percent) <= TOLERANCE,
              "okunan %{:.1f}".format(percent))

        state = vision.bar_state(img, geom)
        check("{}: renk durumu '{}'".format(fname, expected_state),
              state == expected_state, "okunan '{}'".format(state))

    # Eski (renge bağlı) yöntem mor barda çöküyor mu? Düzeltmenin sebebi bu.
    if os.path.exists(os.path.join(ORNEKLER, "malice.png")):
        img = crop(load("malice.png"), (19, 33, 210, 54))
        kirmizi = (30, 30, 200)          # normal.png'den ölçülen HP rengi
        eski = vision.bar_percent(img, kirmizi, ratio_full=0.9)
        check("malice.png: eski yöntem tam dolu barı kaybediyor (hatanın kanıtı)",
              eski < 10.0, "eski yöntem %{:.1f}".format(eski))

    # ------------------------------------------------------------------ parti
    if os.path.exists(os.path.join(ORNEKLER, PARTY_FILE)):
        img = load(PARTY_FILE)
        x0, y0, x1, y1 = PARTY_RECT
        row_h = (y1 - y0) / 2.0
        rows = []
        for index in range(len(PARTY_EXPECTED)):
            top = y0 + int(round(index * row_h))
            bottom = y0 + int(round((index + 1) * row_h))
            if bottom > img.shape[0]:
                break
            rows.append(np.ascontiguousarray(img[top:bottom, x0:x1]))

        geoms = [vision.detect_bar_geometry(rows[i], None) for i in (0, 1)]
        check("parti: iki üyenin geometrisi çıkarıldı",
              geoms[0] is not None and geoms[1] is not None)
        if geoms[0] is not None and geoms[1] is not None:
            width = x1 - x0
            fark = max(abs(geoms[0].x0f - geoms[1].x0f),
                       abs(geoms[0].x1f - geoms[1].x1f)) * width
            check("parti: iki üyenin barı aynı yerde (kayıt doğrulaması)",
                  fark <= 3.0, "fark {:.1f} px".format(fark))

            geom = vision.BarGeometry(
                (geoms[0].x0f + geoms[1].x0f) / 2.0,
                (geoms[0].x1f + geoms[1].x1f) / 2.0,
                (geoms[0].y0f + geoms[1].y0f) / 2.0,
                (geoms[0].y1f + geoms[1].y1f) / 2.0,
            )
            for index, row in enumerate(rows):
                beklenen = PARTY_EXPECTED[index]
                okunan = vision.bar_percent_by_empty(row, geom)
                check("parti üye {}: can %{:.0f}".format(index + 1, beklenen),
                      abs(okunan - beklenen) <= TOLERANCE,
                      "okunan %{:.1f}".format(okunan))
                check("parti üye {}: satır üye olarak tanındı".format(index + 1),
                      vision.band_row_present(row, geom))

    print("\n" + "=" * 60)
    failed = [n for n, ok in RESULTS if not ok]
    print("Toplam {} kontrol, {} başarısız".format(len(RESULTS), len(failed)))
    for name in failed:
        print("  BASARISIZ: " + name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
