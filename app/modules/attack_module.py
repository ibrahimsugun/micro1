"""Atak sekmesi: skill sırası, R sayacı, RPR çekici ve hedef arama (Z).

İç tık 50 ms; skill aralığı tek global gecikme + rastgele ektir. Rastgele tiki
kapalıyken bile +-%10 doğal sapma uygulanır.
"""

import random
import time

from ..constants import (
    ATTACK_NATURAL_JITTER,
    ATTACK_RANDOM_MAX_DEFAULT,
    CALIB_RPR,
    CALIB_TARGET,
    DEFAULT_LOOP_MS,
    MOB_ALIVE_RATIO,
    MODULE_ATTACK,
    NO_PAGE,
    R_ATTACK_INTERVAL_MS,
    RPR_REPEAT_MS,
    TARGET_PRESENT_RATIO,
    Z_MAX_MS,
    Z_MIN_MS,
)
from ..core import vision
from ..core.module_base import ModuleBase

SKILL_ROW_COUNT = 6


def default_skills():
    return [{"enabled": False, "key": "", "fpage": NO_PAGE} for _ in range(SKILL_ROW_COUNT)]


DEFAULT_CONFIG = {
    "skills": None,                  # default_skills() ile doldurulur
    "delay_ms": 800,
    "random_enabled": True,
    "random_max": ATTACK_RANDOM_MAX_DEFAULT,
    "r_enabled": True,
    "rpr_enabled": False,
    "rpr_key": "",
    "rpr_fpage": NO_PAGE,
    "no_z_until_dead": False,
}


class AttackModule(ModuleBase):
    module_id = MODULE_ATTACK

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, DEFAULT_LOOP_MS["attack"], parent)
        config = dict(DEFAULT_CONFIG)
        config["skills"] = default_skills()
        self._config = config
        self._skill_index = 0
        self._next_skill_at = 0.0
        self._next_r_at = 0.0
        self._next_z_at = 0.0
        self._next_rpr_at = 0.0

    # ------------------------------------------------------------------ ayarlar
    def set_config(self, config):
        merged = dict(DEFAULT_CONFIG)
        merged["skills"] = default_skills()
        for key, value in (config or {}).items():
            if key == "skills":
                rows = default_skills()
                for i, row in enumerate(value or []):
                    if i >= SKILL_ROW_COUNT:
                        break
                    rows[i].update(row or {})
                merged["skills"] = rows
            elif key in merged:
                merged[key] = value
        self._config = merged

    def config(self):
        out = dict(self._config)
        out["skills"] = [dict(r) for r in self._config["skills"]]
        return out

    def required_now(self):
        needed = [CALIB_TARGET]
        if self._config.get("rpr_enabled"):
            needed.append(CALIB_RPR)
        return needed

    # ------------------------------------------------------------------ zamanlama
    def _skill_delay(self) -> float:
        cfg = self._config
        base = max(0.0, float(cfg.get("delay_ms", 800)))
        if cfg.get("random_enabled"):
            base += random.uniform(0.0, max(0.0, float(cfg.get("random_max", 0))))
        jitter = 1.0 + random.uniform(-ATTACK_NATURAL_JITTER, ATTACK_NATURAL_JITTER)
        return (base * jitter) / 1000.0

    @staticmethod
    def _z_delay() -> float:
        return random.uniform(Z_MIN_MS, Z_MAX_MS) / 1000.0

    # ------------------------------------------------------------------ döngü
    def on_activate(self):
        now = time.monotonic()
        self._skill_index = 0
        self._next_skill_at = now
        self._next_r_at = now
        self._next_z_at = now
        self._next_rpr_at = now

    def tick(self):
        cfg = self._config
        now = time.monotonic()

        percent = self.ctx.bar_percent(CALIB_TARGET)
        if percent is None:
            percent = 0.0
        has_target = percent > TARGET_PRESENT_RATIO

        self._handle_rpr(cfg, now)

        if has_target:
            self._handle_skills(cfg, now)
            self._handle_r(cfg, now)
            return

        # Hedef yok: skill dongusu ve R durur, yalniz Z ile hedef aranir.
        self._handle_z(cfg, now, percent)

    # ------------------------------------------------------------------ parçalar
    def _handle_skills(self, cfg, now):
        if now < self._next_skill_at:
            return
        skills = cfg["skills"]
        order = [i for i, row in enumerate(skills)
                 if row.get("enabled") and row.get("key")]
        if not order:
            return
        if self._skill_index >= len(order):
            self._skill_index = 0
        row = skills[order[self._skill_index]]
        self._skill_index = (self._skill_index + 1) % len(order)
        self.ctx.input.press_with_page(row.get("fpage", NO_PAGE), row["key"].upper())
        self._next_skill_at = time.monotonic() + self._skill_delay()

    def _handle_r(self, cfg, now):
        if not cfg.get("r_enabled"):
            return
        if now < self._next_r_at:
            return
        self.ctx.input.press_key("R")
        self._next_r_at = time.monotonic() + (R_ATTACK_INTERVAL_MS / 1000.0)

    def _handle_z(self, cfg, now, percent):
        if now < self._next_z_at:
            return
        if cfg.get("no_z_until_dead") and percent > MOB_ALIVE_RATIO:
            self._next_z_at = now + 0.1        # bar bosalana kadar bekle
            return
        self.ctx.input.press_key("Z")
        self._next_z_at = time.monotonic() + self._z_delay()

    def _handle_rpr(self, cfg, now):
        if not cfg.get("rpr_enabled"):
            return
        key = (cfg.get("rpr_key") or "").upper()
        if not key or now < self._next_rpr_at:
            return
        # Renk tabanlı tespit: kılıcın yönü / hangi el / animasyon fark etmez.
        if not self.ctx.rpr_broken():
            return
        self.ctx.input.press_with_page(cfg.get("rpr_fpage", NO_PAGE), key)
        self._next_rpr_at = time.monotonic() + (RPR_REPEAT_MS / 1000.0)
