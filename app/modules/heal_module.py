"""Priest sekmesi: tekli heal ve parti heal.

Tekli heal "Partiye bas" tiki KAPALIYKEN yalnız kendi HP'sine bakar ve tıklama
yapmaz; ACIKKEN eşik altındaki en düşük HP'li üyeye TEK tık atip heal tuşuna
basar ve fare tıklanan yerde KALIR.
"""

import time

from ..constants import (
    CALIB_HP,
    CALIB_PARTY,
    DEFAULT_LOOP_MS,
    HEAL_MEMBER_COOLDOWN_MS,
    MODULE_HEAL,
    NO_PAGE,
)
from ..core.module_base import ModuleBase

DEFAULT_CONFIG = {
    "single": {
        "enabled": False, "threshold": 70, "key": "", "fpage": NO_PAGE,
        "party_click": False,
    },
    "party": {
        "enabled": False, "threshold": 60, "key": "", "fpage": NO_PAGE,
        "trigger_count": 3,
    },
}


class HealModule(ModuleBase):
    module_id = MODULE_HEAL
    # Tamamen ekran okumasiyla calisir: yeni kare gelmeden tekrar donmez.
    # Bekleme sayaclari monotonic tabanli oldugu icin bundan etkilenmez.
    frame_driven = True

    def __init__(self, ctx, party_tracker, parent=None):
        super().__init__(ctx, DEFAULT_LOOP_MS["heal"], parent)
        self.party = party_tracker
        self._config = {k: dict(v) for k, v in DEFAULT_CONFIG.items()}
        self._member_last = {}       # uye indeksi -> son heal (monotonic)

    # ------------------------------------------------------------------ ayarlar
    def set_config(self, config):
        merged = {k: dict(v) for k, v in DEFAULT_CONFIG.items()}
        for section, values in (config or {}).items():
            if section in merged:
                merged[section].update(values or {})
        self._config = merged

    def config(self):
        return {k: dict(v) for k, v in self._config.items()}

    def required_now(self):
        cfg = self._config
        needed = []
        if cfg["single"].get("enabled"):
            if cfg["single"].get("party_click"):
                needed.append(CALIB_PARTY)
            else:
                needed.append(CALIB_HP)
        if cfg["party"].get("enabled"):
            needed.append(CALIB_PARTY)
        return needed

    # ------------------------------------------------------------------ döngü
    def on_activate(self):
        self._member_last.clear()

    def tick(self):
        cfg = self._config
        single = cfg["single"]
        party = cfg["party"]

        if single.get("enabled") or party.get("enabled"):
            if single.get("party_click") or party.get("enabled"):
                self.party.update()

        if single.get("enabled"):
            if single.get("party_click"):
                self._heal_lowest_member(single, float(single.get("threshold", 70)))
            else:
                self._heal_self(single)

        if party.get("enabled"):
            threshold = float(party.get("threshold", 60))
            trigger = max(1, int(party.get("trigger_count", 1)))
            if self.party.count_below(threshold) >= trigger:
                self._heal_lowest_member(party, threshold)

    # ------------------------------------------------------------------ parçalar
    def _heal_self(self, row):
        key = (row.get("key") or "").upper()
        if not key:
            return
        hp = self.ctx.bar_percent(CALIB_HP)
        if hp is None or hp > float(row.get("threshold", 70)):
            return
        self.ctx.input.press_with_page(row.get("fpage", NO_PAGE), key)

    def _heal_lowest_member(self, row, threshold):
        key = (row.get("key") or "").upper()
        if not key:
            return
        member = self.party.lowest_below(threshold)
        if member is None:
            return
        index = member["index"]
        now = time.monotonic()
        last = self._member_last.get(index, 0.0)
        if (now - last) * 1000.0 < HEAL_MEMBER_COOLDOWN_MS:
            return
        x, y = member["center"]
        if not self.ctx.input.click(x, y):
            return
        self.ctx.input.press_with_page(row.get("fpage", NO_PAGE), key)
        self._member_last[index] = time.monotonic()
