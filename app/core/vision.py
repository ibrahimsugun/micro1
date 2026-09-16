"""Görüntü ölçümleri. TÜM girdiler BGR'dir (mss BGRA döndürür -> tuzak #3).

Bar okuma yöntemi "bölge oranı"dır: kayıt anında örneklenen referans renge
maske uygulanır, eşleşen piksel oranı ratio_full ile normalize edilir.

Maske HSV tabanlıdır (gerçek oyun geri bildirimi): KO'nun MP barı degrade
mavi ve boşalan kısmı koyu mavi kalıyor. Düz BGR toleransı koyu-boş kısmı da
"dolu" sayıyordu. Ton (hue) referansla eşleşen AMA yeterince doygun ve parlak
pikseller sayılır; degrade tonları geçer, boşalan koyu kısım elenir.
Referans renk griye yakınsa (ton anlamsız) eski BGR toleransına düşülür.
"""

from collections import namedtuple

import numpy as np

from ..constants import (
    BAR_BAND_MIN_ROWS,
    BAR_COLUMN_EMPTY_FRACTION,
    BAR_DARK_VALUE_MAX,
    BAR_LIT_SAT_MIN,
    BAR_LIT_VALUE_MIN,
    COLOR_TOLERANCE,
    HP_STATES,
    HP_STATE_HUE_TOLERANCE,
    PRESENCE_STD_MIN,
    TEMPLATE_MATCH_THRESHOLD,
)

try:
    import cv2

    CV2_AVAILABLE = True
except Exception:                                    # pragma: no cover
    CV2_AVAILABLE = False

# HSV maske eşikleri (0-255 ölçeğinde S ve V, 0-180 ölçeğinde H)
HUE_TOLERANCE = 16          # referans tona uzaklık (dairesel)
SAT_MIN_ABS = 60            # bunun altı "grimsi" sayılır (ton güvenilmez)
SAT_MIN_FRACTION = 0.40     # doygunluk >= ref doygunluğunun bu katı
VAL_MIN_FRACTION = 0.45     # parlaklık >= ref parlaklığının bu katı
DARK_VALUE_MAX = 60         # "çok karanlık" eşiği (boş bar tespiti)

# RPR (yanık silah) için DAR renk bandı. Referans SABİT yanık kırmızısıdır
# (RPR_BURNT_COLOR_BGR ~ HSV 1,204,150). Yanık silah efekti CANLI ve PARLAKTIR;
# donuk kırmızı-kahve TOPRAK (düşük doygunluk / koyu) yanlış alarm vermesin
# diye doygunluk ve parlaklık bandı ölçülen yanık aralığına (S 147-241,
# V 128-183; 10 gerçek görüntü) oturtulmuştur. Ton dar tutulur.
RPR_HUE_TOLERANCE = 11
RPR_SAT_FRACTION = 0.75
RPR_VAL_LOW = 0.80
RPR_VAL_HIGH = 1.35


# ---------------------------------------------------------------------- HSV
def _bgr_to_hsv(img):
    """BGR (H,W,3) -> H (0-180 float), S (0-255 float), V (0-255 float).

    numpy ile yazıldı: cv2 yalnız RPR için zorunludur (tuzak #6), bar okuma
    cv2'siz de çalışmalıdır.
    """
    arr = img[:, :, :3].astype(np.float32)
    b, g, r = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    delta = maxc - minc

    hue = np.zeros_like(maxc)
    nz = delta > 0
    # OpenCV ölçeği: H = derece / 2 (0-180)
    rmax = nz & (maxc == r)
    gmax = nz & (maxc == g) & ~rmax
    bmax = nz & (maxc == b) & ~rmax & ~gmax
    hue[rmax] = (60.0 * ((g[rmax] - b[rmax]) / delta[rmax]) % 360.0) / 2.0
    hue[gmax] = (60.0 * ((b[gmax] - r[gmax]) / delta[gmax]) + 120.0) / 2.0
    hue[bmax] = (60.0 * ((r[bmax] - g[bmax]) / delta[bmax]) + 240.0) / 2.0

    sat = np.zeros_like(maxc)
    vnz = maxc > 0
    sat[vnz] = (delta[vnz] / maxc[vnz]) * 255.0
    return hue, sat, maxc


def _ref_hsv(ref_color):
    """Tek BGR rengin (h, s, v) üçlüsü."""
    px = np.array([[list(ref_color[:3])]], dtype=np.uint8)
    h, s, v = _bgr_to_hsv(px)
    return float(h[0, 0]), float(s[0, 0]), float(v[0, 0])


def _hue_distance(hue, ref_hue):
    """Dairesel ton uzaklığı (0-90)."""
    diff = np.abs(hue - ref_hue)
    return np.minimum(diff, 180.0 - diff)


def is_grayish(ref_color) -> bool:
    """Referans renk griye yakın mı? (ton güvenilmez -> BGR toleransı kullan)"""
    if not ref_color:
        return True
    _h, s, v = _ref_hsv(ref_color)
    return s < SAT_MIN_ABS or v < 40


def bar_mask(img, ref_color, tol=COLOR_TOLERANCE):
    """Bar 'dolu' piksellerinin boolean maskesi.

    Renkli referans: ton eşleşmesi + doygunluk/parlaklık alt sınırı (degrade
    dayanıklı, boşalan koyu kısmı dışlar). Grimsi referans: eski BGR toleransı.
    """
    if img is None or img.size == 0 or not ref_color:
        return None
    if is_grayish(ref_color):
        return color_mask(img, ref_color, tol)
    ref_h, ref_s, ref_v = _ref_hsv(ref_color)
    hue, sat, val = _bgr_to_hsv(img)
    return (
        (_hue_distance(hue, ref_h) <= HUE_TOLERANCE)
        & (sat >= max(SAT_MIN_ABS, ref_s * SAT_MIN_FRACTION))
        & (val >= ref_v * VAL_MIN_FRACTION)
    )


def hue_match_mask(img, ref_color, hue_tol=HUE_TOLERANCE):
    """Yalnız ton eşleşmesi (varlık tespiti için gevşek maske)."""
    if img is None or img.size == 0 or not ref_color:
        return None
    if is_grayish(ref_color):
        return color_mask(img, ref_color, COLOR_TOLERANCE)
    ref_h, _s, _v = _ref_hsv(ref_color)
    hue, sat, _val = _bgr_to_hsv(img)
    return (_hue_distance(hue, ref_h) <= hue_tol) & (sat >= SAT_MIN_ABS)


def hsv_band_mask(img, ref_color, hue_tol=RPR_HUE_TOLERANCE,
                  sat_frac=RPR_SAT_FRACTION, val_lo=RPR_VAL_LOW,
                  val_hi=RPR_VAL_HIGH):
    """Referans rengin DAR bir HSV bandına düşen pikseller.

    Tonun yanı sıra doygunluk ve parlaklık da referansa yakın olmak zorunda.
    Böylece "kırmızıya benzeyen her şey" değil, kaydedilen rengin kendisi
    yakalanır: arka plan hangi renk olursa olsun (yeşil çayır, mavi su,
    kırmızımsı arazi) yanık silahın kendi kırmızısı ayırt edilir.
    """
    if img is None or img.size == 0 or not ref_color:
        return None
    if is_grayish(ref_color):
        return color_mask(img, ref_color, COLOR_TOLERANCE)
    ref_h, ref_s, ref_v = _ref_hsv(ref_color)
    hue, sat, val = _bgr_to_hsv(img)
    return (
        (_hue_distance(hue, ref_h) <= hue_tol)
        & (sat >= max(SAT_MIN_ABS, ref_s * sat_frac))
        & (val >= ref_v * val_lo)
        & (val <= min(255.0, ref_v * val_hi))
    )


def color_presence_ratio(img, ref_color, hue_tol=RPR_HUE_TOLERANCE) -> float:
    """Referans renk bandına düşen piksellerin oranı (0.0 - 1.0).

    Şekilden ve YÖNDEN bağımsızdır: yalnız renge bakar. RPR'de kılıcın yönü,
    hangi elde olduğu ve animasyonla kımıldaması sonucu değiştirmez; tek elde
    yanık varsa oran yaklaşık yarıya iner ama sıfırlanmaz.
    """
    mask = hsv_band_mask(img, ref_color, hue_tol)
    if mask is None or mask.size == 0:
        return 0.0
    return float(np.count_nonzero(mask)) / float(mask.size)


def dark_mask(img, value_max=DARK_VALUE_MAX):
    """Çok karanlık piksellerin maskesi (boşalmış bar / çerçeve içi)."""
    if img is None or img.size == 0:
        return None
    _h, _s, val = _bgr_to_hsv(img)
    return val <= float(value_max)


# ---------------------------------------------------------------------- BGR
def color_mask(img, ref_color, tol=COLOR_TOLERANCE):
    """Referans renge (BGR) tol içinde kalan piksellerin boolean maskesi."""
    if img is None or img.size == 0 or not ref_color:
        return None
    arr = img.astype(np.int16)
    ref = np.array([int(c) for c in ref_color[:3]], dtype=np.int16)
    diff = np.abs(arr[:, :, :3] - ref)
    return np.all(diff <= int(tol), axis=2)


# ------------------------------------------------------------------- ölçüm
def match_ratio(img, ref_color, tol=COLOR_TOLERANCE) -> float:
    """Bar maskesiyle eşleşen piksel oranı (0.0 - 1.0)."""
    mask = bar_mask(img, ref_color, tol)
    if mask is None or mask.size == 0:
        return 0.0
    return float(np.count_nonzero(mask)) / float(mask.size)


def bar_percent(img, ref_color, tol=COLOR_TOLERANCE, ratio_full=1.0) -> float:
    """Bar doluluk yüzdesi (0 - 100)."""
    ratio = match_ratio(img, ref_color, tol)
    full = float(ratio_full) if ratio_full else 1.0
    if full <= 0.0:
        full = 1.0
    return max(0.0, min(100.0, (ratio / full) * 100.0))


def fill_fraction_by_column(img, ref_color, tol=COLOR_TOLERANCE,
                            column_min=0.2) -> float:
    """Barın soldan kaçıncı sütuna kadar dolu olduğunu yüzde olarak tahmin eder.

    Yalnızca KAYIT ÖNCESİ canlı önizleme içindir: kenarlık ve bar üzerindeki
    yazı gibi sabit kayıplardan etkilenmez, çünkü alan değil GENİŞLİK ölçer.
    Gerçek ölçüm yöntemi bölge oranıdır (bar_percent).
    """
    mask = bar_mask(img, ref_color, tol)
    if mask is None or mask.size == 0:
        return 0.0
    filled = mask.mean(axis=0) >= float(column_min)
    hits = np.nonzero(filled)[0]
    if hits.size == 0:
        return 0.0
    return max(0.0, min(100.0, (float(hits[-1]) + 1.0) / mask.shape[1] * 100.0))


# ---------------------------------------------------------------- örnekleme
def dominant_color(img, tol=COLOR_TOLERANCE):
    """Bölgenin baskın rengini (BGR) örnekler."""
    if img is None or img.size == 0:
        return None
    return _dominant_of(img.reshape(-1, 3), tol)


def saturated_dominant_color(img, tol=COLOR_TOLERANCE, prefer_hue=None):
    """Yalnız DOYGUN ve PARLAK pikseller arasından baskın renk.

    Bar kayıtlarında kullanılır: koyu arka plan, çerçeve ve yazı piksellerinin
    baskın rengi ele geçirmesini engeller. prefer_hue verilirse (0-180) o tona
    yakın doygun pikseller önceliklidir (parti barı için hp_bar tonu).
    Hiç doygun piksel yoksa düz dominant_color'a düşer.
    """
    if img is None or img.size == 0:
        return None
    hue, sat, val = _bgr_to_hsv(img)
    flat = img.reshape(-1, 3)
    good = (sat.reshape(-1) >= SAT_MIN_ABS) & (val.reshape(-1) >= 70)
    if prefer_hue is not None:
        near = good & (_hue_distance(hue.reshape(-1), float(prefer_hue)) <= HUE_TOLERANCE)
        if np.count_nonzero(near) >= max(20, flat.shape[0] // 200):
            good = near
    if not np.any(good):
        return dominant_color(img, tol)
    return _dominant_of(flat[good], tol)


def vivid_dominant_color(img, percentile=99.0, sat_fraction=0.80):
    """Bölgedeki en CANLI (doygun) piksel kümesinin baskın rengi.

    RPR bölgesinde silah küçük, arka plan büyüktür: "en sık renk" arka planı
    verir. Yanık silah ise bölgedeki en doygun renktir; bu yüzden önce
    doygunluk tavanı bulunup yalnız ona yakın pikseller arasından örneklenir.
    Yeterince canlı piksel yoksa normal örnekleyiciye düşer.
    """
    if img is None or img.size == 0:
        return None
    _hue, sat, val = _bgr_to_hsv(img)
    flat = img.reshape(-1, 3)
    s_flat = sat.reshape(-1)
    v_flat = val.reshape(-1)
    ceiling = float(np.percentile(s_flat, percentile))
    threshold = max(SAT_MIN_ABS, ceiling * sat_fraction)
    good = (s_flat >= threshold) & (v_flat >= 60)
    if np.count_nonzero(good) < 12:
        return saturated_dominant_color(img)
    return _dominant_of(flat[good], COLOR_TOLERANCE)


def ref_hue(ref_color):
    """Referans BGR rengin tonu (0-180); grimsi ise None."""
    if not ref_color or is_grayish(ref_color):
        return None
    h, _s, _v = _ref_hsv(ref_color)
    return h


def _dominant_of(flat_pixels, tol):
    flat = flat_pixels.astype(np.int16)
    quant = (flat // 16).astype(np.int32)
    keys = quant[:, 0] * 4096 + quant[:, 1] * 64 + quant[:, 2]
    values, counts = np.unique(keys, return_counts=True)
    top = values[int(np.argmax(counts))]
    center = np.array(
        [(top // 4096) * 16 + 8, ((top // 64) % 64) * 16 + 8, (top % 64) * 16 + 8],
        dtype=np.int16,
    )
    near = np.all(np.abs(flat - center) <= int(tol), axis=1)
    if not np.any(near):
        return tuple(int(v) for v in center)
    return tuple(int(v) for v in np.round(flat[near].mean(axis=0)))


# ------------------------------------------------------------------- varlık
def region_present(img, min_std=PRESENCE_STD_MIN) -> bool:
    """Boş satır mı gerçek içerik mi? (std sapma — yalnız düz zeminlerde işe yarar)"""
    if img is None or img.size == 0:
        return False
    return float(np.std(img.astype(np.float32))) >= float(min_std)


def region_std(img) -> float:
    if img is None or img.size == 0:
        return 0.0
    return float(np.std(img.astype(np.float32)))


def party_row_present(img, hp_ref_color, min_fraction=0.50) -> bool:
    """Parti satırında GERÇEKTEN üye var mı?

    Gerçek oyunda boş satırların arkası oyun dünyasıdır (yüksek std) — std
    sapma bu yüzden çalışmaz (SS geri bildirimi: 2 kişilik partide 7 üye).
    Kural: satır piksellerinin (a) HP barı tonuna uyan VEYA (b) çok karanlık
    (panel zemini / boşalmış bar) olma oranı >= min_fraction -> üye var.

    Üye satırı koyu panel + kırmızı bardan oluşur ve orana rahat ulaşır; ölü
    üyenin boş barları da karanlık sınıfına düşer -> tuzak #10 korunur. Oyun
    dünyası (çim, gök, zemin dokusu) ya parlak/karışık renklidir ya da
    doygunluğu düşüktür; iki sınıfa da girmez. MP mavisi ve isim yazısı gibi
    "sayılmayan" pikseller pay bırakılarak eşik %50 tutuldu.
    """
    if img is None or img.size == 0:
        return False
    total = img.shape[0] * img.shape[1]
    if total == 0:
        return False

    combined = np.zeros((img.shape[0], img.shape[1]), dtype=bool)
    dark = dark_mask(img)
    if dark is not None:
        combined |= dark
    if hp_ref_color:
        hp = hue_match_mask(img, hp_ref_color)
        if hp is not None:
            combined |= hp

    return (float(np.count_nonzero(combined)) / float(total)) >= float(min_fraction)


def target_present(img, ref_color, ratio_full=1.0, min_percent=2.0) -> bool:
    """Hedef barında renkli piksel var mı -> hedef var/yok."""
    return bar_percent(img, ref_color, COLOR_TOLERANCE, ratio_full) > float(min_percent)


# -------------------------------------------------------------------- şablon
def template_match(img, template, threshold=TEMPLATE_MATCH_THRESHOLD):
    """(eşleşti, skor). cv2 yoksa (False, 0.0) — RPR kapanır, uygulama çalışır."""
    if not CV2_AVAILABLE or img is None or template is None:
        return False, 0.0
    if img.size == 0 or template.size == 0:
        return False, 0.0
    ih, iw = img.shape[:2]
    th, tw = template.shape[:2]
    if th > ih or tw > iw:
        return False, 0.0
    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    score = float(result.max())
    if not np.isfinite(score):
        # Tamamen düz (varyanssız) bölgede TM_CCOEFF_NORMED NaN üretebilir.
        return False, 0.0
    return score >= float(threshold), score


# ================================================================ TUMDENGELIM
# HP barinin rengi debuff'a gore degisiyor; dolu kismin rengine bakan olcum
# (bar_mask / bar_percent) bu durumda %0 veriyor. Asagidaki yol barin BOS
# kismini sayar: bos kisim rengi ne olursa olsun siyah kalir, bu yuzden olcum
# renkten tamamen bagimsizdir. YALNIZ hp_bar ve party_bar bu yolu kullanir;
# mp_bar, target_bar ve rpr_icon yukaridaki tumevarim yolunda kalir.

# Kalibrasyonda barin sag ucundaki karanlik serit bu orandan kisaysa "cerceve"
# sayilip kirpilir; daha uzunsa "bosalmis bar" sayilip korunur.
BAR_EDGE_TRIM_MAX_FRACTION = 0.08
BAR_DETECT_ROW_RUN = 0.25       # satirda bar-rengi kosusu genisligin bu kati olmali
BAR_DETECT_COL_FILL = 0.50      # sutun dolu sayilsin diye gereken oran
BAR_BAND_CLEAN_FRACTION = 0.90  # olcum seridi: kosusu tepenin bu katindan uzun satirlar


class BarGeometry(namedtuple("BarGeometry", "x0f x1f y0f y1f")):
    """Barin kayitli bolge icindeki yeri - KESIRLI (0.0-1.0).

    Kesirli tutulur ki cozunurluk ve DPI degisse de ayni kalsin (parti satir
    yuksekliginin kesirli tutulmasiyla ayni gerekce). x ekseni dolu/bos
    sinirinin tarandigi aralik; y ekseni ise olcum SERIDI - barin ustundeki
    cerceve parlakligi ve ortasindaki "1466/2916" yazisi disarida birakilir.
    """

    __slots__ = ()

    def to_list(self):
        return [round(float(v), 6) for v in self]

    @classmethod
    def from_list(cls, data):
        """Profilden okunan listeyi dogrular; bozuksa None (eski profil guvenli)."""
        if not data or len(data) != 4:
            return None
        try:
            geom = cls(*(float(v) for v in data))
        except (TypeError, ValueError):
            return None
        if not (0.0 <= geom.x0f < geom.x1f <= 1.0):
            return None
        if not (0.0 <= geom.y0f < geom.y1f <= 1.0):
            return None
        return geom

    def crop(self, img):
        """Bolge goruntusunden olcum dikdortgenini keser (kopya degil, view)."""
        if img is None or img.size == 0:
            return None
        h, w = img.shape[:2]
        x0 = max(0, min(w - 1, int(round(self.x0f * w))))
        x1 = max(x0 + 1, min(w, int(round(self.x1f * w))))
        y0 = max(0, min(h - 1, int(round(self.y0f * h))))
        y1 = max(y0 + 1, min(h, int(round(self.y1f * h))))
        return img[y0:y1, x0:x1]


def value_of(img):
    """Parlaklik kanali (V) - uint8, float'a hic cevirmeden.

    _bgr_to_hsv'nin aksine ton ve doygunluk hesaplamaz: tek gecis, bolme yok.
    Tumdengelim olcumunun tamami bu kanalla yapilir (olculen kazanc ~3.2x).
    """
    if img is None or img.size == 0:
        return None
    return img[:, :, :3].max(axis=2)


def empty_column_mask(img, geom=None, dark_max=BAR_DARK_VALUE_MAX,
                      column_fraction=BAR_COLUMN_EMPTY_FRACTION):
    """Olcum seridindeki her sutun icin "bos mu" maskesi.

    Sutun karari ORAN ile verilir, tek piksele bakilmaz: bar uzerindeki yazinin
    siyah konturu dolu sutunlara karanlik piksel serpiyor (olculdu: dolu bir
    sutunun %47'sine kadar). Serit yazinin disindan secildigi icin pay genistir.
    """
    band = geom.crop(img) if geom is not None else img
    val = value_of(band)
    if val is None or val.size == 0:
        return None
    return (val <= int(dark_max)).mean(axis=0) >= float(column_fraction)


def bar_percent_by_empty(img, geom=None, dark_max=BAR_DARK_VALUE_MAX,
                         column_fraction=BAR_COLUMN_EMPTY_FRACTION) -> float:
    """Bar dolulugu (0-100) - barin BOS kismindan tumdengelimle. Renge BAKMAZ.

    "En sagdaki dolu sutun" yerine bos sutun ORANI sayilir: sinir arama tek bir
    parlak sutunda %100'e sicrarken oran sayimi kademeli bozulur (gercek oyun
    goruntulerinde olculen sapma +-3 puan).
    """
    empty = empty_column_mask(img, geom, dark_max, column_fraction)
    if empty is None or empty.size == 0:
        return 0.0
    return max(0.0, min(100.0, (1.0 - float(empty.mean())) * 100.0))


def bar_hue(img, geom=None):
    """Barin DOLU kismindaki baskin ton (0-180); okunamiyorsa None.

    Kirmizi 0/180 sinirinda sarildigi icin duz medyan yanlis sonuc verir
    (0 ile 179 tonlarinin medyani ~90, yani camgobegi cikar). Bu yuzden
    DAIRESEL ortalama kullanilir. Bos kisim karanlik, yazi ise doygunsuz
    oldugu icin ikisi de kendiliginden elenir.
    """
    band = geom.crop(img) if geom is not None else img
    if band is None or band.size == 0:
        return None
    hue, sat, val = _bgr_to_hsv(band)
    mask = (sat >= BAR_LIT_SAT_MIN) & (val >= BAR_LIT_VALUE_MIN)
    if np.count_nonzero(mask) < 8:
        return None
    ang = np.deg2rad(hue[mask].astype(np.float64) * 2.0)
    x = float(np.cos(ang).mean())
    y = float(np.sin(ang).mean())
    if (x * x + y * y) < 0.25:            # tonlar dagink -> guvenilmez
        return None
    return float((np.degrees(np.arctan2(y, x)) % 360.0) / 2.0)


def classify_hue(hue, tolerance=HP_STATE_HUE_TOLERANCE):
    """Tonu HP_STATES tablosundaki en yakin duruma esler; uzaksa None.

    Tolerans dar tutulur (8): olculen en yakin cift normal(0) ile yanma(17.6),
    aradaki mesafe 17.6. Mevcut HUE_TOLERANCE (16) bu ikisini karistirirdi.
    """
    if hue is None:
        return None
    best_key, best_dist = None, None
    for key, _label, ref in HP_STATES:
        diff = abs(float(hue) - float(ref))
        dist = min(diff, 180.0 - diff)
        if best_dist is None or dist < best_dist:
            best_key, best_dist = key, dist
    if best_dist is None or best_dist > float(tolerance):
        return None
    return best_key


def band_row_present(img, geom, min_fraction=0.90) -> bool:
    """Parti satirinda gercekten uye var mi - RENKTEN BAGIMSIZ.

    Uyenin HP bandi ya ISIKLIDIR (canli; rengi kirmizi, mor, turuncu farketmez)
    ya da tamamen KARANLIKTIR (olu). Oyun dunyasi ikisine de girmez: doku
    orta parlaklikta ve dagiliktir. Eski party_row_present kayitli KIRMIZI
    tona bakiyordu; debuff'li bir partide (ornekler/ klasorundeki gercek
    ekran goruntusunde yedi uyenin de bari turuncuydu) tum uyeler kaybolurdu.
    """
    band = geom.crop(img) if geom is not None else img
    if band is None or band.size == 0:
        return False
    arr = band[:, :, :3].astype(np.int16)
    maxc = arr.max(axis=2)
    minc = arr.min(axis=2)
    sat = np.where(maxc > 0, (maxc - minc) * 255 // np.maximum(maxc, 1), 0)
    lit = (sat >= BAR_LIT_SAT_MIN) & (maxc >= BAR_LIT_VALUE_MIN)
    dark = maxc <= BAR_DARK_VALUE_MAX
    known = float(np.count_nonzero(lit | dark)) / float(maxc.size)
    return known >= float(min_fraction)


def bar_state(img, geom=None, tolerance=HP_STATE_HUE_TOLERANCE):
    """Barin renk durumu anahtari; taninmiyorsa None. YALNIZ bilgi amaclidir."""
    return classify_hue(bar_hue(img, geom), tolerance)


# --------------------------------------------------- geometri cikarma (kayit)
def _runs(mask):
    """1-B boolean dizideki True kosularinin (baslangiclar, bitisler) ciftleri."""
    padded = np.concatenate(([False], np.asarray(mask, dtype=bool), [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return edges[0::2], edges[1::2]


def _longest_run(mask):
    """En uzun kesintisiz True araligi -> (baslangic, bitis), yari acik."""
    starts, ends = _runs(mask)
    if starts.size == 0:
        return 0, 0
    best = int(np.argmax(ends - starts))
    return int(starts[best]), int(ends[best])


def _longest_run_len(mask) -> int:
    """En uzun kesintisiz True kosusunun uzunlugu."""
    starts, ends = _runs(mask)
    return int((ends - starts).max()) if starts.size else 0


def detect_bar_geometry(img, ref_color=None):
    """Bolge goruntusunden barin yerini cikarir. YALNIZ kalibrasyonda calisir.

    Kaydedilen sey "kirmizi ne kadar yer kapliyor" (oran) DEGIL, "bar nerede"
    (dikdortgen) bilgisidir: oran renge baglidir ve mor barla coker, dikdortgen
    ise renkten de cozunurlukten de bagimsizdir.

    Olcum seridini (y ekseni) yazinin DISINDAN secer: bar uzerindeki
    "1466/2916" yazisi ve siyah konturu olcumu bozmasin diye.
    """
    if img is None or img.size == 0:
        return None
    h, w = img.shape[:2]
    if h < 4 or w < 8:
        return None

    # Referans ton: kayitli renk varsa ondan, yoksa SOL seritten orneklenir.
    # Bar soldan doldugu icin sol serit, canin hangi seviyede oldugundan
    # bagimsiz olarak doludur (calibration_tab'daki kayit-oncesi ile ayni fikir).
    if ref_color is None or is_grayish(ref_color):
        strip = max(2, int(w * 0.15))
        ref_color = saturated_dominant_color(img[:, :strip])
    if not ref_color or is_grayish(ref_color):
        return None
    ref_h, _s, _v = _ref_hsv(ref_color)

    hue, sat, val = _bgr_to_hsv(img)
    fill = (
        (_hue_distance(hue, ref_h) <= HUE_TOLERANCE)
        & (sat >= SAT_MIN_ABS)
        & (val >= BAR_LIT_VALUE_MIN)
    )
    dark = val <= BAR_DARK_VALUE_MAX

    # 1) Barin SATIR araligi: her satirdaki EN UZUN kesintisiz bar-rengi kosusu.
    #    Oran yerine kosu uzunlugu kullanilir; boylece kullanici cerceveyi genis
    #    cizse de (bolgenin yarisi oyun dunyasi olsa da) ve can dusuk olsa da
    #    bar satirlari bulunur. Yazi kosuyu boler, bu yuzden esik yuksek degil.
    need = max(8, int(w * BAR_DETECT_ROW_RUN))
    runs = np.fromiter((_longest_run_len(fill[y]) for y in range(h)),
                       dtype=np.int32, count=h)
    ry0, ry1 = _longest_run(runs >= need)
    if ry1 - ry0 < BAR_BAND_MIN_ROWS:
        return None

    # 2) Olcum SERIDI: bar renginin KESINTISIZ aktigi satirlar, yani uzerinde
    #    YAZI olmayan satirlar. Kosusu tepe degerin BAR_BAND_CLEAN_FRACTION
    #    katindan kisa olan satirda yazi vardir ve disarida birakilir.
    #    Sabit bir "ust" ya da "alt" kurali ise yanlis olurdu: ana barda can
    #    yazisi dikey ORTALI, parti satirinda uye ADI ALTTA duruyor.
    #    Serit sutun sinirindan ONCE belirlenir, cunku yazi tam dolu/bos
    #    sinirinin uzerine dusup bari ikiye bolebiliyor.
    peak = int(runs[ry0:ry1].max())
    clean = np.zeros(h, dtype=bool)
    clean[ry0:ry1] = runs[ry0:ry1] >= peak * BAR_BAND_CLEAN_FRACTION
    by0, by1 = _longest_run(clean)
    if by1 - by0 < BAR_BAND_MIN_ROWS:
        # Hicbir satir tam temiz degil (yazi tum yuksekligi kapliyor): en az
        # satir sayisina ulasana kadar bar satirlari icinde genislet.
        by0 = max(ry0, min(by0, ry1 - BAR_BAND_MIN_ROWS))
        by1 = min(ry1, by0 + BAR_BAND_MIN_ROWS)
    if by1 - by0 < BAR_BAND_MIN_ROWS:
        return None

    # 3) Kesin SUTUN araligi: yazisiz seritte her sutun ya dolu ya bostur.
    #    Oyun dunyasi ikisine de girmez, boylece cercevenin disi elenir.
    band = slice(by0, by1)
    col_fill = fill[band].mean(axis=0)
    col_dark = dark[band].mean(axis=0)
    # ZARF: ilk ve son "bar sutunu". Kesintisiz kosu aranmaz; can yazisinin
    # beyaz halesi ve barin acik gri cerceve cizgisi araya ne dolu ne karanlik
    # sutunlar sokuyor ve kosu aramasi bari ikiye boluyordu. Bu bosluklar
    # zaten barin ICINDE oldugu icin zarfa dahil edilir.
    barish = np.flatnonzero((col_fill >= BAR_DETECT_COL_FILL)
                            | (col_dark >= BAR_DETECT_COL_FILL))
    if barish.size < 8:
        return None
    cx0, cx1 = int(barish[0]), int(barish[-1]) + 1
    if cx1 - cx0 < 8:
        return None
    filled = np.flatnonzero(col_fill[cx0:cx1] >= BAR_DETECT_COL_FILL)
    if filled.size == 0:
        return None

    # Bastaki karanlik sutunlar cercevedir (bar soldan dolar) -> kirpilir.
    cx0 += int(filled[0])
    # Sondaki karanlik serit KISAysa cerceve, UZUNsa bosalmis bardir. Kisa
    # olani kirpariz; uzun olana dokunulmaz, yoksa bos kisim yok sayilir.
    tail = (cx1 - cx0) - (int(filled[-1]) + 1 - int(filled[0]))
    if 0 < tail <= max(1, int((cx1 - cx0) * BAR_EDGE_TRIM_MAX_FRACTION)):
        cx1 -= tail
    if cx1 - cx0 < 8:
        return None

    return BarGeometry(cx0 / float(w), cx1 / float(w), by0 / float(h), by1 / float(h))
