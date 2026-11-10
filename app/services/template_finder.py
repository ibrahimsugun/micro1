"""Çok ölçekli şablon arama (DC çerçevesi, Confirm, launcher START, ID kutusu, OTP).

Şablonlar farklı ekran ölçeklerinde alındı (ör. DC şablonları 1280x800
mantıksal görüntüden, program ise DPI farkında olduğu için oyunu 1600x1000
fiziksel piksel görüyor → ölçek 1.25). Bu yüzden birkaç ölçek denenir; bir
şablon için bulunan en iyi ölçek hatırlanır ve sonraki aramalarda ÖNCE o
denenir (yeterli skor gelirse diğerlerine bakılmaz → hızlı).
"""

import os
import sys
import threading

import cv2

SCALES = (1.0, 1.25, 0.8, 1.1, 0.9, 1.5, 0.75, 1.33, 0.67, 1.75, 2.0)


def templates_dir() -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "app", "templates")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "templates")


class Match:
    __slots__ = ("score", "x", "y", "w", "h", "scale")

    def __init__(self, score, x, y, w, h, scale):
        self.score, self.x, self.y, self.w, self.h, self.scale = score, x, y, w, h, scale

    def center(self):
        return self.x + self.w // 2, self.y + self.h // 2

    def point(self, ox, oy):
        """Şablon İÇİNDEKİ (orijinal ölçekte) bir noktayı kare koordinatına çevirir."""
        return self.x + int(round(ox * self.scale)), self.y + int(round(oy * self.scale))

    def __repr__(self):
        return "Match(%.3f @ %d,%d x%.2f)" % (self.score, self.x, self.y, self.scale)


class TemplateFinder:
    def __init__(self, folder=None):
        self._folder = folder or templates_dir()
        self._cache = {}
        self._resized = {}
        self._best_scale = {}
        self._lock = threading.Lock()

    def template(self, name):
        with self._lock:
            if name not in self._cache:
                path = os.path.join(self._folder, name + ".png")
                image = cv2.imread(path, cv2.IMREAD_COLOR)
                if image is None:
                    raise FileNotFoundError(path)
                self._cache[name] = image
            return self._cache[name]

    def _scaled(self, name, scale):
        key = (name, scale)
        with self._lock:
            cached = self._resized.get(key)
        if cached is not None:
            return cached
        base = self.template(name)
        image = base if scale == 1.0 else cv2.resize(
            base, None, fx=scale, fy=scale,
            interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
        with self._lock:
            self._resized[key] = image
        return image

    def find(self, frame, name, threshold=0.8):
        """En iyi eşleşme (skor eşiği geçerse) ya da None."""
        if frame is None:
            return None
        if frame.ndim == 3 and frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        known = self._best_scale.get(name)
        order = ([known] if known else []) + [s for s in SCALES if s != known]
        best = None
        for scale in order:
            tmpl = self._scaled(name, scale)
            th, tw = tmpl.shape[:2]
            if th > frame.shape[0] or tw > frame.shape[1]:
                continue
            result = cv2.matchTemplate(frame, tmpl, cv2.TM_CCOEFF_NORMED)
            _, score, _, loc = cv2.minMaxLoc(result)
            if best is None or score > best.score:
                best = Match(float(score), loc[0], loc[1], tw, th, scale)
            if scale == known and score >= threshold:
                break                      # bilinen ölçek tuttu: yeter
        if best is None or best.score < threshold:
            return None
        self._best_scale[name] = best.scale
        return best
