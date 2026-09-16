"""Modül thread'lerinin okuduğu paylaşımlı kapılar.

threading.Event kullanılır; okuma kilitsizdir, yazma GUI thread'inden yapılır.
"""

import threading


class AppState:
    def __init__(self):
        self.master_on = threading.Event()      # ana açma/kapama
        self.panic = threading.Event()          # panik tuşu: her şey durur
        self.game_focused = threading.Event()   # oyun penceresi önde mi
        self.player_dead = threading.Event()    # ölüm koruması aktif mi
        self.resolution_ok = threading.Event()  # çözünürlük kalibrasyonla uyumlu
        self.resolution_ok.set()

    def modules_may_run(self) -> bool:
        """Modüllerin ekran okuyup tuş göndermesine izin var mı?"""
        return (
            self.master_on.is_set()
            and not self.panic.is_set()
            and self.game_focused.is_set()
            and not self.player_dead.is_set()
            and self.resolution_ok.is_set()
        )

    def input_allowed(self) -> bool:
        """Girdi gönderimi için tek kapı (panik her şeyi keser)."""
        return not self.panic.is_set()

    def reason_blocked(self) -> str:
        if self.panic.is_set():
            return "Panik"
        if not self.master_on.is_set():
            return "Master kapalı"
        if not self.resolution_ok.is_set():
            return "Çözünürlük değişti"
        if not self.game_focused.is_set():
            return "Oyun odakta değil"
        if self.player_dead.is_set():
            return "Ölüm koruması"
        return ""
