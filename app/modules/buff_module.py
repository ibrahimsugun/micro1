"""Priest sekmesi: 6 buff satırı, bağımsız sayaçlar, KENDİ ana tiki.

Buff modülü priest heal tikinden bağımsız açılır/kapanır. Parti üyeliği
değişse bile sayaçlar sıfırlanmaz.
"""

import time

from ..constants import DEFAULT_LOOP_MS, MODULE_BUFF, NO_PAGE
from ..core.module_base import ModuleBase

BUFF_ROW_COUNT = 4


def default_rows():
    return [
        {"enabled": False, "key": "", "fpage": NO_PAGE, "duration": 600}
        for _ in range(BUFF_ROW_COUNT)
    ]


class BuffModule(ModuleBase):
    module_id = MODULE_BUFF

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, DEFAULT_LOOP_MS["buff"], parent)
        self._rows = default_rows()
        self._next_due = [0.0] * BUFF_ROW_COUNT

    # ------------------------------------------------------------------ ayarlar
    def set_rows(self, rows):
        merged = default_rows()
        for i, row in enumerate(rows or []):
            if i >= BUFF_ROW_COUNT:
                break
            merged[i].update(row or {})
        self._rows = merged

    def rows(self):
        return [dict(r) for r in self._rows]

    def required_now(self):
        return []

    def remaining_seconds(self):
        """UI için: her satırın kalan süresi (kapalı satırlarda None)."""
        now = time.monotonic()
        out = []
        for i, row in enumerate(self._rows):
            if not row.get("enabled"):
                out.append(None)
            else:
                out.append(max(0.0, self._next_due[i] - now))
        return out

    # ------------------------------------------------------------------ döngü
    def on_activate(self):
        # Modül açıldığında tüm aktif buff'lar hemen basılsın.
        self._next_due = [0.0] * BUFF_ROW_COUNT

    def tick(self):
        now = time.monotonic()
        for i, row in enumerate(self._rows):
            if not row.get("enabled"):
                continue
            key = (row.get("key") or "").upper()
            if not key:
                continue
            if now < self._next_due[i]:
                continue
            if self.ctx.input.press_with_page(row.get("fpage", NO_PAGE), key):
                duration = max(1, int(row.get("duration", 600)))
                self._next_due[i] = time.monotonic() + duration
