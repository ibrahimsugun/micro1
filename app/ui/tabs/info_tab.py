"""Bilgi sekmesi: canlı değerler, parti ve modül durum panosu.

Loglama yoktur (performans kararı); burada görülen her şey RAM içindeki
LiveStatus tablosundan gelir.
"""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..theme import CARD_SPACING, GREEN, MUTED, RED, TEXT
from ..widgets.card import Card, field_label
from ..widgets.status_board_widget import StatusBoardWidget


class InfoTab(QWidget):
    testKeyRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(CARD_SPACING + 1)

        live_box = Card("Canlı değerler", self)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        self._values = {}
        for row, (key, caption) in enumerate((
            ("hp", "HP"), ("hp_state", "Durum"), ("mp", "MP"),
            ("target", "Hedef"), ("rpr", "RPR"), ("party_count", "Parti üye"),
        )):
            grid.addWidget(field_label(caption, live_box), row, 0)
            value = QLabel("—", live_box)
            value.setStyleSheet("font-weight: 600;")
            grid.addWidget(value, row, 1)
            self._values[key] = value
        grid.setColumnStretch(1, 1)
        live_box.add_layout(grid)
        root.addWidget(live_box)

        party_box = Card("Parti üyeleri", self)
        self._party_layout = QGridLayout()
        self._party_layout.setContentsMargins(0, 0, 0, 0)
        self._party_layout.setHorizontalSpacing(8)
        self._party_layout.setVerticalSpacing(3)
        self._party_layout.setColumnStretch(1, 1)
        self._party_labels = []
        party_box.add_layout(self._party_layout)
        root.addWidget(party_box)

        self.board = StatusBoardWidget(self)
        root.addWidget(self.board)

        system_box = Card("Sistem", self)
        system = QGridLayout()
        system.setContentsMargins(0, 0, 0, 0)
        system.setHorizontalSpacing(8)
        system.setVerticalSpacing(4)
        system.addWidget(field_label("Girdi arka ucu", system_box), 0, 0)
        self.backend_label = QLabel("—", system_box)
        self.backend_label.setToolTip(
            "Interception sürücüsü bulunduysa donanım seviyesinde tuş "
            "gönderilir; aksi halde PyAutoGUI/win32 yedeği kullanılır."
        )
        system.addWidget(self.backend_label, 0, 1)
        system.addWidget(field_label("Ekran tarayıcı", system_box), 1, 0)
        self.scanner_label = QLabel("—", system_box)
        system.addWidget(self.scanner_label, 1, 1)
        system.addWidget(field_label("Oyun penceresi", system_box), 2, 0)
        self.window_label = QLabel("—", system_box)
        self.window_label.setWordWrap(True)
        system.addWidget(self.window_label, 2, 1)
        system.setColumnStretch(1, 1)
        system_box.add_layout(system)

        self.test_key_button = QPushButton("Test tuşu gönder", system_box)
        self.test_key_button.setToolTip(
            "Girdi yolunu denemek için 3 saniye sonra 'A' tuşunu gönderir. "
            "Tamam'a bastıktan sonra Not Defteri gibi bir pencereye geç: harf "
            "oraya düşüyorsa arka uç çalışıyor demektir. Oyun penceresi "
            "kontrolüne takılmaz, yalnız panik açıkken çalışmaz."
        )
        self.test_key_button.clicked.connect(self.testKeyRequested)
        system_box.add(self.test_key_button)
        root.addWidget(system_box)
        root.addStretch(1)

    # ------------------------------------------------------------------ güncelle
    @staticmethod
    def _percent_text(value):
        return "—" if value is None else "%{:.0f}".format(value)

    def update_values(self, snapshot, scanner_backend="", window_title="",
                      window_focused=False):
        self._values["hp"].setText(self._percent_text(snapshot.get("hp_percent")))
        # Renk durumu yalnız bilgi: hiçbir modül kararına bağlı değil.
        state = snapshot.get("hp_state")
        state_label = self._values["hp_state"]
        state_label.setText(snapshot.get("hp_state_label") or "—")
        state_label.setStyleSheet("font-weight: 600; color: {};".format(
            MUTED if state in (None, "normal") else RED
        ))
        self._values["mp"].setText(self._percent_text(snapshot.get("mp_percent")))

        target_on = snapshot.get("target_present")
        target = self._values["target"]
        target.setText(
            "VAR · %{:.0f}".format(snapshot.get("target_percent", 0.0))
            if target_on else "yok"
        )
        target.setStyleSheet(
            "font-weight: 600; color: {};".format(GREEN if target_on else MUTED)
        )

        rpr = snapshot.get("rpr_broken")
        rpr_ratio = snapshot.get("rpr_ratio")
        suffix = "" if rpr_ratio is None else " · yanık %{:.1f}".format(rpr_ratio * 100)
        rpr_label = self._values["rpr"]
        rpr_label.setText(("KIRIK" if rpr else "sağlam") + suffix)
        rpr_label.setStyleSheet(
            "font-weight: 600; color: {};".format(RED if rpr else GREEN)
        )

        members = snapshot.get("party") or []
        self._values["party_count"].setText(str(len(members)))
        self._sync_party(members)

        self.backend_label.setText(snapshot.get("input_backend", "—"))
        self.scanner_label.setText("{} · {:.1f} fps".format(
            scanner_backend or "—", snapshot.get("scanner_fps", 0.0)
        ))
        self.window_label.setText(window_title or "ayarlanmadı")
        self.window_label.setStyleSheet(
            "color: {};".format(GREEN if window_focused else RED)
        )
        self.window_label.setToolTip(
            "odakta" if window_focused else "odakta değil"
        )

    def _sync_party(self, members):
        while len(self._party_labels) < len(members):
            index = len(self._party_labels)
            name = field_label("Üye {}".format(index + 1))
            value = QLabel("—")
            value.setStyleSheet("font-weight: 600; color: {};".format(TEXT))
            self._party_layout.addWidget(name, index, 0)
            self._party_layout.addWidget(value, index, 1)
            self._party_labels.append((name, value))
        for index, (name, value) in enumerate(self._party_labels):
            if index < len(members):
                name.show()
                value.show()
                member = members[index]
                state = member.get("state")
                suffix = "" if state in (None, "normal") else "  · " + str(state)
                value.setText("%{:.0f}{}".format(member.get("percent", 0.0), suffix))
                value.setStyleSheet("font-weight: 600; color: {};".format(
                    TEXT if state in (None, "normal") else RED
                ))
            else:
                name.hide()
                value.hide()

    def set_module_state(self, module_id, state, detail=""):
        self.board.set_state(module_id, state, detail)
