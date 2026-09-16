"""Ölüm koruması.

HP 5 saniye boyunca %0 kalır veya HP barı tamamen kaybolursa modüller duraklar
ve bip çalar; HP geri geldiğinde otomatik devam edilir.
"""

import time

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from ..constants import BEEP_DEATH, DEATH_HOLD_SECONDS, DEATH_RECOVER_PERCENT


class DeathGuard(QObject):
    deathDetected = pyqtSignal()
    recovered = pyqtSignal()

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._zero_since = None
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def reset(self):
        self._zero_since = None
        if self.ctx.state.player_dead.is_set():
            self.ctx.state.player_dead.clear()

    def _tick(self):
        if not self.ctx.state.master_on.is_set():
            self.reset()
            return

        snapshot = self.ctx.live.snapshot()
        hp = snapshot.get("hp_percent")
        present = snapshot.get("hp_present", False)

        if hp is None:
            return                       # HP barı kalibre edilmemiş -> koruma yok

        dead_signal = (not present) or hp <= 0.5
        now = time.monotonic()

        if dead_signal:
            if self._zero_since is None:
                self._zero_since = now
            elif (now - self._zero_since) >= DEATH_HOLD_SECONDS:
                if not self.ctx.state.player_dead.is_set():
                    self.ctx.state.player_dead.set()
                    self.ctx.sound.beep(BEEP_DEATH)
                    self.deathDetected.emit()
            return

        self._zero_since = None
        if self.ctx.state.player_dead.is_set() and hp >= DEATH_RECOVER_PERCENT:
            self.ctx.state.player_dead.clear()
            self.recovered.emit()
