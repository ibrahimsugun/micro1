"""Genel sekmesi: HP potu, MP potu, Minör ve 3. içecek.

Satırlar BAĞIMSIZ ateşler (minör ile pot aynı anda basabilir); tek kısıt aynı
POT TUŞU için 1320 ms bekleme süresidir.
"""

import time

from ..constants import (
    CALIB_HP,
    CALIB_MP,
    DEFAULT_LOOP_MS,
    MODULE_POT,
    NO_PAGE,
    POT_KEY_COOLDOWN_MS,
)
from ..core.module_base import ModuleBase

ROW_HP = "hp"
ROW_MP = "mp"
ROW_MINOR = "minor"

DEFAULT_CONFIG = {
    ROW_HP: {"enabled": False, "threshold": 50, "key": "1", "fpage": NO_PAGE},
    ROW_MP: {"enabled": False, "threshold": 50, "key": "2", "fpage": NO_PAGE},
    ROW_MINOR: {"enabled": False, "threshold": 70, "key": "3"},
}


class PotModule(ModuleBase):
    module_id = MODULE_POT
    # Tamamen ekran okumasiyla calisir: yeni kare gelmeden tekrar donmez.
    # Bekleme sayaclari monotonic tabanli oldugu icin bundan etkilenmez.
    frame_driven = True

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, DEFAULT_LOOP_MS["pot"], parent)
        self._config = {k: dict(v) for k, v in DEFAULT_CONFIG.items()}
        self._key_last = {}          # tuş -> son basım (monotonic)

    # ------------------------------------------------------------------ ayarlar
    def set_config(self, config):
        """UI'da yeni sözlük yaratılıp tek referans atamasıyla takas edilir."""
        merged = {k: dict(v) for k, v in DEFAULT_CONFIG.items()}
        for row, values in (config or {}).items():
            if row in merged:
                merged[row].update(values or {})
        self._config = merged

    def config(self):
        return {k: dict(v) for k, v in self._config.items()}

    def required_now(self):
        cfg = self._config
        needed = []
        if any(cfg[r].get("enabled") for r in (ROW_HP, ROW_MINOR)):
            needed.append(CALIB_HP)
        if cfg[ROW_MP].get("enabled"):
            needed.append(CALIB_MP)
        return needed

    # ------------------------------------------------------------------ döngü
    def on_activate(self):
        self._key_last.clear()

    def tick(self):
        cfg = self._config
        now = time.monotonic()

        needs_hp = any(cfg[r].get("enabled") for r in (ROW_HP, ROW_MINOR))
        hp = self.ctx.bar_percent(CALIB_HP) if needs_hp else None
        mp = self.ctx.bar_percent(CALIB_MP) if cfg[ROW_MP].get("enabled") else None

        if hp is not None:
            self._maybe_fire(cfg[ROW_HP], hp, now)
            self._maybe_fire(cfg[ROW_MINOR], hp, now)
        if mp is not None:
            self._maybe_fire(cfg[ROW_MP], mp, now)

    def _maybe_fire(self, row, percent, now):
        if not row.get("enabled"):
            return
        key = (row.get("key") or "").upper()
        if not key:
            return
        if percent > float(row.get("threshold", 0)):
            return
        last = self._key_last.get(key, 0.0)
        if (now - last) * 1000.0 < POT_KEY_COOLDOWN_MS:
            return
        if self.ctx.input.press_with_page(row.get("fpage", NO_PAGE), key):
            self._key_last[key] = time.monotonic()
