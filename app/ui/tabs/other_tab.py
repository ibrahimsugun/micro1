"""Diğer sekmesi: tıklama + tuş kaydedici ve oynatıcı (mouseRepeater portu)."""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QInputDialog,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...constants import DEFAULT_LOOP_MS, MODULE_CLICKER
from ...modules.clicker_module import describe
from ..theme import CARD_SPACING, GREEN, RED
from ..widgets.card import Card, hint_label
from ..widgets.common import HotkeyButton
from ..widgets.module_header import ModuleHeader


class OtherTab(QWidget):
    changed = pyqtSignal()

    def __init__(self, manager, hotkey_service, recorder, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.module = manager.get(MODULE_CLICKER)
        self.recorder = recorder
        self._profiles = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(CARD_SPACING + 1)

        self.header = ModuleHeader(
            "Diğer · tıklayıcı", MODULE_CLICKER, hotkey_service,
            DEFAULT_LOOP_MS["clicker"], self,
        )
        root.addWidget(self.header)

        # --- denetimler -----------------------------------------------------
        control_box = Card("Kayıt / oynatma", self)
        control_box.add(hint_label(
            "Oynatmanın çalışması için Master açık, bu modülün tiki açık ve "
            "oyun penceresi odakta olmalıdır.", control_box,
        ))

        buttons = QGridLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setHorizontalSpacing(6)
        self.record_button = QPushButton("Kayıt", control_box)
        self.record_button.setToolTip(
            "Fare tıklamalarını ve klavye tuşlarını gecikmeleriyle kaydeder."
        )
        self.stop_button = QPushButton("Durdur", control_box)
        self.stop_button.setToolTip("Kaydı veya oynatmayı durdurur.")
        self.play_button = QPushButton("Oynat", control_box)
        self.play_button.setToolTip(
            "Kayıtlı adımları sırayla oynatır. Konum ±3 px, gecikme ×0.9-1.1 "
            "aralığında rastgeleleştirilir."
        )
        for column, button in enumerate(
            (self.record_button, self.stop_button, self.play_button)
        ):
            buttons.addWidget(button, 0, column)
            buttons.setColumnStretch(column, 1)
        control_box.add_layout(buttons)

        self.record_hotkey = HotkeyButton(
            "Kayıt", hotkey_service, "clicker::record", control_box
        )
        self.stop_hotkey = HotkeyButton(
            "Durdur", hotkey_service, "clicker::stop", control_box
        )
        self.play_hotkey = HotkeyButton(
            "Oynat", hotkey_service, "clicker::play", control_box
        )
        for button in (self.record_hotkey, self.stop_hotkey, self.play_hotkey):
            control_box.add(button)

        self.repeat_check = QCheckBox("Sürekli tekrarla", control_box)
        self.repeat_check.setChecked(True)
        self.repeat_check.setToolTip(
            "Liste bitince baştan başlar. Kapalıyken bir kez oynatır."
        )
        control_box.add(self.repeat_check)
        root.addWidget(control_box)

        # --- adım listesi ---------------------------------------------------
        list_box = Card("Kayıtlı adımlar", self)
        self.action_list = QListWidget(list_box)
        self.action_list.setToolTip("Kaydedilen tıklama ve tuşların sırası.")
        self.action_list.setMinimumHeight(110)
        list_box.add(self.action_list)
        self.clear_button = QPushButton("Listeyi temizle", list_box)
        self.clear_button.setObjectName("ghost")
        self.clear_button.setToolTip("Tüm kayıtlı adımları siler.")
        list_box.add(self.clear_button)
        root.addWidget(list_box, 1)

        # --- profiller ------------------------------------------------------
        profile_box = Card("Tıklama profilleri", self)
        profile_box.setToolTip(
            "Adım listelerini isimlendirip saklar. Ayarlar dosyasına yalnızca "
            "Kaydet düğmesiyle yazılır."
        )
        self.profile_combo = QComboBox(profile_box)
        self.profile_combo.setToolTip("Kayıtlı adım listeleri.")
        profile_box.add(self.profile_combo)

        profile_buttons = QGridLayout()
        profile_buttons.setContentsMargins(0, 0, 0, 0)
        profile_buttons.setHorizontalSpacing(6)
        self.profile_load = QPushButton("Yükle", profile_box)
        self.profile_load.setToolTip(
            "Seçili profildeki adımları listeye yükler (mevcut liste gider)."
        )
        self.profile_save = QPushButton("Farklı kaydet", profile_box)
        self.profile_save.setToolTip(
            "Şu anki adım listesini yeni bir isimle saklar."
        )
        self.profile_delete = QPushButton("Sil", profile_box)
        self.profile_delete.setToolTip("Seçili tıklama profilini siler.")
        for column, button in enumerate(
            (self.profile_load, self.profile_save, self.profile_delete)
        ):
            profile_buttons.addWidget(button, 0, column)
            profile_buttons.setColumnStretch(column, 1)
        profile_box.add_layout(profile_buttons)
        root.addWidget(profile_box)

        # --- bağlantılar ----------------------------------------------------
        self.record_button.clicked.connect(self.start_recording)
        self.stop_button.clicked.connect(self.stop_all)
        self.play_button.clicked.connect(self.start_playback)
        self.clear_button.clicked.connect(self._clear_actions)
        self.repeat_check.toggled.connect(self._on_repeat)
        self.profile_load.clicked.connect(self._load_profile)
        self.profile_save.clicked.connect(self._save_profile)
        self.profile_delete.clicked.connect(self._delete_profile)
        for button in (self.record_hotkey, self.stop_hotkey, self.play_hotkey):
            button.keyChanged.connect(self._on_hotkey_changed)

        self.recorder.actionsChanged.connect(self.refresh_list)
        self.module.stepChanged.connect(self._highlight_step)

        self.header.enabledChanged.connect(self._on_toggle)
        self.header.hotkeyChanged.connect(lambda _: self.changed.emit())
        self.header.loopChanged.connect(self._on_loop)

    # ------------------------------------------------------------------ eylem
    def _mark(self, button, color):
        button.setStyleSheet(
            "" if color is None
            else "color: {}; font-weight: 700;".format(color)
        )

    def start_recording(self):
        self.recorder.set_ignored_keys([
            self.record_hotkey.key(), self.stop_hotkey.key(), self.play_hotkey.key(),
        ])
        if self.recorder.start():
            self._mark(self.record_button, RED)

    def stop_all(self):
        self.recorder.stop()
        self.module.stop_playback()
        self._mark(self.record_button, None)
        self._mark(self.play_button, None)

    def start_playback(self):
        self.recorder.stop()
        self._mark(self.record_button, None)
        self.module.set_actions(self.recorder.actions())
        self.module.set_repeat(self.repeat_check.isChecked())
        if not self.module.start_playback():
            QMessageBox.information(
                self, "Tıklayıcı", "Önce en az bir adım kaydetmelisin."
            )
            return
        self._mark(self.play_button, GREEN)

    def _clear_actions(self):
        self.recorder.clear()
        self.module.set_actions([])
        self.changed.emit()

    def _on_repeat(self, value):
        self.module.set_repeat(value)
        self.changed.emit()

    def _on_hotkey_changed(self, _norm):
        self.changed.emit()

    def _highlight_step(self, index):
        if 0 <= index < self.action_list.count():
            self.action_list.setCurrentRow(index)

    def _fill_list(self):
        self.action_list.clear()
        for i, action in enumerate(self.recorder.actions()):
            self.action_list.addItem("{}. {}".format(i + 1, describe(action)))

    def refresh_list(self):
        self._fill_list()
        self.module.set_actions(self.recorder.actions())
        self.changed.emit()

    # ------------------------------------------------------------------ profil
    def _refresh_profiles(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(sorted(self._profiles.keys()))
        self.profile_combo.blockSignals(False)

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Tıklama profili", "Profil adı:")
        name = (name or "").strip()
        if not ok or not name:
            return
        self._profiles[name] = self.recorder.actions()
        self._refresh_profiles()
        index = self.profile_combo.findText(name)
        if index >= 0:
            self.profile_combo.setCurrentIndex(index)
        self.changed.emit()

    def _load_profile(self):
        name = self.profile_combo.currentText()
        if not name or name not in self._profiles:
            return
        self.recorder.set_actions(self._profiles[name])
        self.refresh_list()

    def _delete_profile(self):
        name = self.profile_combo.currentText()
        if not name or name not in self._profiles:
            return
        del self._profiles[name]
        self._refresh_profiles()
        self.changed.emit()

    # ------------------------------------------------------------------ modül
    def _on_toggle(self, checked):
        ok = self.manager.request_enable(MODULE_CLICKER, checked)
        if checked and not ok:
            self.header.set_checked_silently(False)
        self.changed.emit()

    def _on_loop(self, value):
        self.module.set_loop_ms(value)
        self.changed.emit()

    def apply(self):
        self.module.set_actions(self.recorder.actions())
        self.module.set_repeat(self.repeat_check.isChecked())

    def clicker_hotkeys(self) -> dict:
        return {
            "clicker_record": self.record_hotkey.key(),
            "clicker_stop": self.stop_hotkey.key(),
            "clicker_play": self.play_hotkey.key(),
        }

    def action_keys(self):
        return []

    def to_dict(self) -> dict:
        return {
            "enabled": self.header.is_checked(),
            "hotkey": self.header.hotkey_value(),
            "loop_ms": self.header.loop_ms(),
            "repeat": self.repeat_check.isChecked(),
            "actions": self.recorder.actions(),
            "record_hotkey": self.record_hotkey.key(),
            "stop_hotkey": self.stop_hotkey.key(),
            "play_hotkey": self.play_hotkey.key(),
            "profiles": self._profiles,
        }

    def from_dict(self, data):
        data = data or {}
        self.repeat_check.blockSignals(True)
        self.repeat_check.setChecked(bool(data.get("repeat", True)))
        self.repeat_check.blockSignals(False)
        self.record_hotkey.set_key(data.get("record_hotkey", ""))
        self.stop_hotkey.set_key(data.get("stop_hotkey", ""))
        self.play_hotkey.set_key(data.get("play_hotkey", ""))
        self._profiles = dict(data.get("profiles") or {})
        self._refresh_profiles()
        self.recorder.set_actions(data.get("actions") or [])
        self._fill_list()
        self.header.set_hotkey(data.get("hotkey", ""))
        self.header.set_loop_ms(data.get("loop_ms", DEFAULT_LOOP_MS["clicker"]))
        self.module.set_loop_ms(self.header.loop_ms())
        self.header.set_checked_silently(bool(data.get("enabled", False)))
        self.apply()

    def pending_enabled(self) -> bool:
        return self.header.is_checked()

    def set_state(self, state):
        self.header.set_state(state)

    def force_unchecked(self):
        self.header.set_checked_silently(False)
