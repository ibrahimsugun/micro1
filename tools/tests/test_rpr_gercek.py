"""RPR gerçek görsel testi: kullanıcının yanık silah ekran görüntüleri.

tools/tests/ornekler/rpr_yanik altındaki 10 gerçek kare, farklı arka planlarda
(kahve, ahşap, çimen, buz, taş) ve farklı ellerde YANIK silahı gösterir. Sabit
yanık kırmızısının (RPR_BURNT_COLOR_BGR) bu gerçek karelerin HEPSİNDE yanığı
yakaladığını doğrular. Renk/eşik ayarı ileride bozulursa bu test yakalar.

Çevrimdışıdır: pencere açmaz, yalnız kayıtlı PNG okur.
"""

import glob
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.constants import RPR_BURNT_COLOR_BGR      # noqa: E402
from app.core import vision                        # noqa: E402

BURNT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "ornekler", "rpr_yanik")
# Görseller tam kare (karakter + silah); silah küçük olduğu için oran düşüktür.
# Eşik güvenli-düşük: yanığın YAKALANDIĞINI doğrular, kayıt oranını değil.
MIN_RATIO = 0.005

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("[{}] {}{}".format("PASS" if ok else "FAIL", name,
                             ("  -- " + detail) if detail else ""))


def load(path):
    with open(path, "rb") as handle:
        buf = np.frombuffer(handle.read(), dtype=np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def main():
    files = sorted(glob.glob(os.path.join(BURNT_DIR, "*.png")))
    check("Yanık silah örnekleri bulundu (>=10)", len(files) >= 10,
          "{} dosya".format(len(files)))

    for path in files:
        img = load(path)
        if img is None:
            check("Okunabildi: {}".format(os.path.basename(path)), False)
            continue
        ratio = vision.color_presence_ratio(img, RPR_BURNT_COLOR_BGR)
        check("Yanık yakalandı: {}".format(os.path.basename(path)),
              ratio >= MIN_RATIO, "oran %{:.2f}".format(ratio * 100))

    print("\n" + "=" * 60)
    failed = [n for n, ok in RESULTS if not ok]
    print("Toplam {} kontrol, {} başarısız".format(len(RESULTS), len(failed)))
    for name in failed:
        print("  BASARISIZ: " + name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
