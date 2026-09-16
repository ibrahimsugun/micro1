"""Bip sesleri. winsound.Beep senkron çalışır → tek atımlık thread'de çalınır."""

import threading

try:
    import winsound

    WINSOUND_AVAILABLE = True
except Exception:                                    # pragma: no cover
    WINSOUND_AVAILABLE = False


class SoundService:
    def __init__(self, enabled: bool = True):
        self.enabled = bool(enabled)

    def beep(self, spec):
        """spec = (frekans Hz, süre ms)"""
        if not self.enabled or not WINSOUND_AVAILABLE:
            return
        freq, dur = spec
        threading.Thread(
            target=self._play, args=(int(freq), int(dur)), daemon=True
        ).start()

    @staticmethod
    def _play(freq, dur):
        try:
            winsound.Beep(freq, dur)
        except Exception:
            pass
