"""Kalibrasyon kaydı veri modeli ve JSON dönüşümleri."""

import base64

import numpy as np

from ..core.vision import BarGeometry

try:
    import cv2

    CV2_AVAILABLE = True
except Exception:                                    # pragma: no cover
    CV2_AVAILABLE = False


class CalibrationRegion:
    """Tek bir kayıtlı bölge: dikdörtgen + referans renk (veya şablon görüntü)."""

    def __init__(self, name, rect=None, ref_color=None, ratio_full=1.0,
                 template_b64="", saved=False, bar_geom=None):
        self.name = name
        self.rect = tuple(int(v) for v in rect) if rect else None
        self.ref_color = tuple(int(v) for v in ref_color) if ref_color else None
        self.ratio_full = float(ratio_full)
        self.template_b64 = template_b64 or ""
        self.saved = bool(saved)
        # Barin bolge icindeki yeri (kesirli). DOLU ise okuma renkten bagimsiz
        # tumdengelimle yapilir; None ise eski tumevarim yolu kullanilir.
        # Eski profillerde yoktur -> None -> hicbir sey bozulmaz.
        self.bar_geom = bar_geom
        self._template_cache = None

    # ------------------------------------------------------------------ JSON
    def to_dict(self) -> dict:
        data = {"rect": list(self.rect) if self.rect else None}
        if self.ref_color:
            data["ref_color"] = list(self.ref_color)
            data["ratio_full"] = round(self.ratio_full, 6)
        if self.bar_geom is not None:
            data["bar_geom"] = self.bar_geom.to_list()
        if self.template_b64:
            data["template_b64"] = self.template_b64
        return data

    @classmethod
    def from_dict(cls, name, data) -> "CalibrationRegion":
        data = data or {}
        return cls(
            name=name,
            rect=data.get("rect"),
            ref_color=data.get("ref_color"),
            ratio_full=data.get("ratio_full", 1.0),
            template_b64=data.get("template_b64", ""),
            saved=bool(data.get("rect")),
            bar_geom=BarGeometry.from_list(data.get("bar_geom")),
        )

    # ------------------------------------------------------------------ şablon
    def template(self):
        """base64 PNG -> BGR numpy dizi (önbellekli). cv2 yoksa None."""
        if self._template_cache is not None:
            return self._template_cache
        if not self.template_b64 or not CV2_AVAILABLE:
            return None
        try:
            raw = base64.b64decode(self.template_b64)
            buf = np.frombuffer(raw, dtype=np.uint8)
            img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            self._template_cache = img
            return img
        except Exception:
            return None

    def set_template_from_image(self, img_bgr) -> bool:
        if not CV2_AVAILABLE or img_bgr is None:
            return False
        ok, buf = cv2.imencode(".png", img_bgr)
        if not ok:
            return False
        self.template_b64 = base64.b64encode(buf.tobytes()).decode("ascii")
        self._template_cache = img_bgr.copy()
        return True

    # ------------------------------------------------------------------ yardımcı
    def center(self):
        if not self.rect:
            return None
        x, y, w, h = self.rect
        return (x + w // 2, y + h // 2)

    def summary(self) -> str:
        if not self.rect:
            return "kayıtlı değil"
        x, y, w, h = self.rect
        base = f"{w}x{h} @ ({x}, {y})"
        if self.bar_geom is not None:
            g = self.bar_geom
            base += (f" · bar x %{g.x0f * 100:.0f}-%{g.x1f * 100:.0f}"
                     f" · şerit y %{g.y0f * 100:.0f}-%{g.y1f * 100:.0f}")
        elif self.ref_color:
            b, g, r = self.ref_color
            base += f" · renk RGB({r},{g},{b}) · tam={self.ratio_full * 100:.0f}%"
        elif self.template_b64:
            base += " · şablon görüntü"
        return base
