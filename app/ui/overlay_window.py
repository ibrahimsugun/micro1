"""Oyun üzerinde duran küçük bilgi katmanı (açılıp kapatılabilir).

Tıklamaları geçirir (WindowTransparentForInput) ve ekran yakalamadan çıkarılır,
böylece kendi ölçümlerimizi bozmaz. Ana panelle aynı renk dilini kullanır ama
oyun üzerinde okunsun diye koyu zeminlidir.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from ..constants import MODULE_LABELS
from ..core.module_base import STATE_LABELS
from ..services.capture_shield import exclude_from_capture

STYLE = """
QWidget#overlayRoot {
    background-color: rgba(22, 26, 34, 190);
    border: 1px solid rgba(255, 255, 255, 40);
    border-radius: 8px;
}
QLabel { color: #eef1f6; font-size: 11px; background: transparent; }
QLabel#overlayTitle { color: #9aa4b2; font-size: 10px; font-weight: 700; }
QLabel#overlayMuted { color: #9aa4b2; font-size: 10px; }
"""


class OverlayWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setObjectName("overlayRoot")
        self.setStyleSheet(STYLE)
        self._shielded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        self.title = QLabel("BİRLEŞİK KO", self)
        self.title.setObjectName("overlayTitle")
        self.vitals = QLabel("HP —   MP —", self)
        self.vitals.setStyleSheet("font-size: 13px; font-weight: 700;")
        self.target = QLabel("Hedef —", self)
        self.party = QLabel("Parti —", self)
        self.modules = QLabel("", self)
        self.modules.setObjectName("overlayMuted")
        for label in (self.title, self.vitals, self.target, self.party,
                      self.modules):
            layout.addWidget(label)

        self.resize(190, 108)
        self._place()

    def _place(self):
        """Ekranı 6'ya böler (3 sütun × 2 satır); overlay 2. sütunun başında,
        üst satırda durur. Sabit köşe yerine bu konum, oyunun sol üstteki
        bar/panel bölgesinin dışında kalıp daha görünür oluyor."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.move(30, 30)
            return
        geo = screen.geometry()
        # 2. sütunun başladığı yerin biraz solu (kullanıcı isteği).
        x = geo.x() + geo.width() // 3 - 90
        y = geo.y() + 68                         # üst satırın biraz altı
        self.move(x, y)

    def showEvent(self, event):
        super().showEvent(event)
        self._place()
        if not self._shielded:
            self._shielded = exclude_from_capture(self)

    def update_values(self, snapshot):
        hp = snapshot.get("hp_percent")
        mp = snapshot.get("mp_percent")
        state = snapshot.get("hp_state")
        # "normal" yazılmaz: overlay küçük kalsın, yalnız dikkat çekeni göster.
        # Overlay dar; uzun etiket yerine kısa anahtar yazılır ("mor", "yanma").
        # Tam açıklama Bilgi sekmesinde duruyor.
        state_text = "" if state in (None, "normal") else "  [" + str(state) + "]"
        self.vitals.setText("HP {}{}   MP {}".format(
            "—" if hp is None else "%{:.0f}".format(hp),
            state_text,
            "—" if mp is None else "%{:.0f}".format(mp),
        ))
        self.target.setText(
            "Hedef VAR · %{:.0f}".format(snapshot.get("target_percent", 0.0))
            if snapshot.get("target_present") else "Hedef yok"
        )
        members = snapshot.get("party") or []
        self.party.setText(
            "Parti  " + "  ".join("%{:.0f}".format(m.get("percent", 0.0))
                                  for m in members)
            if members else "Parti —"
        )

        states = snapshot.get("modules") or {}
        parts = []
        for module_id, label in MODULE_LABELS.items():
            info = states.get(module_id)
            if not info or info.get("state") == "stopped":
                continue
            parts.append("{}: {}".format(
                label.split(" ")[0], STATE_LABELS.get(info["state"], "")
            ))
        self.modules.setText("   ".join(parts))
        self.adjustSize()
