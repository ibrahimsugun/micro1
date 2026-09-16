"""Ana pencere.

Yerleşim (üstten alta; ilk dört blok her sekmede sabit kalır):
    [ MASTER · durum · süre ]  [⤡]     ana anahtar + kompakt
    [ HP ][ MP ][ Hedef ][ RPR ]       canlı şerit
    [☐ Üstte tut] [☐ Bip] [☐ Tepsiye küçült]
    [Şeffaflık ───●─── %100]
    [ Genel | Atak | Priest | Diğer | Kalib. | Bilgi ]
    ( sekme içeriği — kartlar, kaydırılabilir )

"Program ayarları" bloğu Genel sekmesinin altına taşınır (kullanıcı kararı).
"""

import time

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStyle,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..constants import (
    APP_NAME,
    CALIB_LABELS,
    MODULE_ATTACK,
    MODULE_BUFF,
    MODULE_CLICKER,
    MODULE_HEAL,
    MODULE_LABELS,
    MODULE_POT,
)
from ..services.hotkey_service import action_key_conflicts, display_name
from ..services.screen_scanner import MODE_SCREEN, MODE_WINDOW
from .live_view_window import LiveViewWindow
from .overlay_window import OverlayWindow
from .tabs.attack_tab import AttackTab
from .tabs.calibration_tab import CalibrationTab
from .tabs.general_tab import GeneralTab
from .tabs.info_tab import InfoTab
from .tabs.other_tab import OtherTab
from .tabs.priest_tab import PriestTab
from .theme import GREEN, GREEN_SOFT, MUTED, RED, RED_SOFT, TEXT
from .widgets.card import Card, field_label, field_row
from .widgets.common import HotkeyButton, PercentSlider, StatusChip

PANEL_WIDTH = 310
PANEL_HEIGHT = 580
OPACITY_MIN = 25        # pencere tamamen görünmez olmasın
NEUTRAL_SOFT = "#e4e9f1"


class MainWindow(QWidget):
    def __init__(self, services, parent=None):
        super().__init__(parent)
        self.ctx = services["ctx"]
        self.manager = services["manager"]
        self.hotkeys = services["hotkeys"]
        self.settings = services["settings"]
        self.window_guard = services["window_guard"]
        self.death_guard = services["death_guard"]
        self.status_reader = services["status_reader"]
        self.party = services["party"]
        self.recorder = services["recorder"]

        self._loading = False
        self._compact = False
        self._active_since = None
        self._warned_conflicts = set()
        self._pending_missing = []
        self._warned_overlap = False
        self._title_autocaptured = False
        self._warned_no_title = False
        self._live_view_wanted = True
        self._warned_elevation = False

        self.setWindowTitle(APP_NAME)
        self.setMinimumWidth(PANEL_WIDTH)
        self.resize(PANEL_WIDTH, PANEL_HEIGHT)

        self.overlay = OverlayWindow()
        self.live_view = LiveViewWindow(self.ctx.scanner)

        self._build_ui()
        self._connect_services()
        self._build_tray()

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(300)
        self.poll_timer.timeout.connect(self._poll)
        self.poll_timer.start()

    # ================================================================== arayüz
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # --- ana anahtar ----------------------------------------------------
        master_row = QHBoxLayout()
        master_row.setSpacing(6)
        self.master_button = QPushButton("MASTER · PASİF", self)
        self.master_button.setObjectName("masterOff")
        self.master_button.setToolTip(
            "Tüm modüllerin ana anahtarı. Kapatıldığında modül tikleri korunur."
        )
        self.master_button.clicked.connect(self._toggle_master)
        master_row.addWidget(self.master_button, 1)

        self.compact_button = QPushButton("⤡", self)
        self.compact_button.setObjectName("iconButton")
        self.compact_button.setFixedWidth(34)
        self.compact_button.setToolTip(
            "Kompakt mod: yalnızca master düğmesi kalır. Aynı düğmeyle geri "
            "dönersin."
        )
        self.compact_button.clicked.connect(
            lambda: self.set_compact(not self._compact)
        )
        master_row.addWidget(self.compact_button)
        root.addLayout(master_row)

        # --- canlı şerit ----------------------------------------------------
        self.chips_row = QWidget(self)
        chips = QHBoxLayout(self.chips_row)
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(5)
        self.chip_hp = StatusChip("HP", self.chips_row)
        self.chip_mp = StatusChip("MP", self.chips_row)
        self.chip_target = StatusChip("Hedef", self.chips_row)
        self.chip_rpr = StatusChip("RPR", self.chips_row)
        for chip in (self.chip_hp, self.chip_mp, self.chip_target, self.chip_rpr):
            chips.addWidget(chip, 1)
        self.chips_row.setToolTip(
            "Canlı okumalar. Kalibrasyonu yapılmamış değerler '—' görünür."
        )
        root.addWidget(self.chips_row)

        # --- her zaman görünen seçenekler -----------------------------------
        self.checks_row = QWidget(self)
        checks = QGridLayout(self.checks_row)
        checks.setContentsMargins(0, 0, 0, 0)
        checks.setHorizontalSpacing(8)
        checks.setVerticalSpacing(4)
        self.on_top_check = QCheckBox("Üstte tut", self.checks_row)
        self.on_top_check.setToolTip("Pencereyi her zaman üst katmanda tutar.")
        self.beep_check = QCheckBox("Bip", self.checks_row)
        self.beep_check.setChecked(True)
        self.beep_check.setToolTip("Ölüm tespiti ve modül hatasında bip çalar.")
        self.tray_check = QCheckBox("Tepsiye küçült", self.checks_row)
        self.tray_check.setChecked(True)
        self.tray_check.setToolTip(
            "Kapat düğmesi programı kapatmak yerine tepsiye küçültür."
        )
        checks.addWidget(self.on_top_check, 0, 0)
        checks.addWidget(self.beep_check, 0, 1)
        checks.addWidget(self.tray_check, 0, 2)
        checks.setColumnStretch(2, 1)

        self.opacity_slider = PercentSlider(
            100, self.checks_row,
            tooltip="Pencerenin saydamlığı. Küçültünce arkasındaki oyun görünür.",
        )
        self.opacity_slider.slider.setRange(OPACITY_MIN, 100)
        checks.addWidget(field_label("Şeffaflık", self.checks_row), 1, 0)
        checks.addWidget(self.opacity_slider, 1, 1, 1, 2)
        root.addWidget(self.checks_row)

        # Durum/uyarı satırı — Genel sekmesinin altına taşınır.
        self.uptime_label = QLabel("Pasif", self)
        self.uptime_label.setAlignment(Qt.AlignCenter)
        self.uptime_label.setToolTip("Master açıldığından beri geçen süre.")

        self._build_settings_box()

        # --- sekmeler -------------------------------------------------------
        self.tabs = QTabWidget(self)
        self.tabs.setToolTip(
            "Genel: potlar · Atak: skill döngüsü · Priest: heal ve buff · "
            "Diğer: tıklama kaydedici · Kalib.: bar kayıtları · "
            "Bilgi: canlı değerler"
        )
        self.general_tab = GeneralTab(self.manager, self.hotkeys, self)
        self.attack_tab = AttackTab(self.manager, self.hotkeys, self)
        self.priest_tab = PriestTab(self.manager, self.hotkeys, self)
        self.other_tab = OtherTab(self.manager, self.hotkeys, self.recorder, self)
        self.calibration_tab = CalibrationTab(self.ctx, self.party, self)
        self.info_tab = InfoTab(self)

        self.general_tab.add_footer(self.uptime_label)
        self.general_tab.add_footer(self.settings_box)

        self._scrolls = {}
        for tab, caption in (
            (self.general_tab, "Genel"),
            (self.attack_tab, "Atak"),
            (self.priest_tab, "Priest"),
            (self.other_tab, "Diğer"),
            (self.calibration_tab, "Kalib."),
            (self.info_tab, "Bilgi"),
        ):
            self.tabs.addTab(self._wrap_scroll(tab), caption)
        root.addWidget(self.tabs, 1)

        self._connect_ui()

    def _build_settings_box(self):
        """Profil / oyun penceresi / kısayollar — Genel sekmesinin altına gider."""
        self.settings_box = Card("Program ayarları", self)
        self.settings_box.setToolTip("Profilden bağımsız program ayarları.")

        self.profile_combo = QComboBox(self.settings_box)
        self.profile_combo.setToolTip(
            "Tüm modül ayarları ve kalibrasyon kayıtları profile bağlıdır."
        )
        self.settings_box.add_layout(field_row(
            field_label("Profil", self.settings_box), self.profile_combo
        ))

        self.new_profile_button = QPushButton("Yeni", self.settings_box)
        self.new_profile_button.setToolTip("Mevcut ayarlarla yeni profil oluşturur.")
        self.save_button = QPushButton("Kaydet", self.settings_box)
        self.save_button.setObjectName("primary")
        self.save_button.setToolTip("Ayarlar dosyaya YALNIZCA bu düğmeyle yazılır.")
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(6)
        buttons.addWidget(self.new_profile_button, 1)
        buttons.addWidget(self.save_button, 1)
        self.settings_box.add_layout(buttons)
        self.settings_box.add_divider()

        self.window_edit = QLineEdit(self.settings_box)
        self.window_edit.setPlaceholderText("ilk master açılışında alınır")
        self.window_edit.setToolTip(
            "Oyun penceresi BAŞLIĞININ bir parçası. Bu başlık ön planda değilse "
            "tarama ve tuş gönderimi durur."
        )
        self.capture_title_button = QPushButton("Yakala", self.settings_box)
        self.capture_title_button.setFixedWidth(64)
        self.capture_title_button.setToolTip(
            "Ön plandaki pencerenin başlığını alır (önce oyuna geç, 3 sn beklenir)."
        )
        self.settings_box.add(field_label("Oyun penceresi", self.settings_box))
        self.settings_box.add_layout(field_row(
            self.window_edit, self.capture_title_button
        ))

        self.master_hotkey = HotkeyButton(
            "Master", self.hotkeys, "app::master", self.settings_box
        )
        self.panic_hotkey = HotkeyButton(
            "Panik", self.hotkeys, "app::panic", self.settings_box
        )
        self.panic_hotkey.setToolTip(
            "Her şeyi anında durdurur. Yalnızca master ile geri açılır."
        )
        self.settings_box.add(self.master_hotkey)
        self.settings_box.add(self.panic_hotkey)

        self.settings_box.add_divider()
        self.overlay_check = QCheckBox("Overlay göster", self.settings_box)
        self.overlay_check.setToolTip(
            "Oyun üzerinde HP/MP, parti, hedef ve modül durumlarını gösteren "
            "küçük katman."
        )
        self.settings_box.add(self.overlay_check)

        self.embed_check = QCheckBox("Arka plan modu", self.settings_box)
        self.embed_check.setToolTip(
            "Görüntü, ekran yerine doğrudan oyun PENCERESİNDEN okunur; oyun "
            "başka pencerelerin arkasında dururken bile tarama sürer.\n\n"
            "Tuş/tık gönderilirken oyun kısa süreliğine (~100 ms) ön plana "
            "alınır, sonra odak geri verilir — bu istemci girdiyi yalnızca "
            "odaktayken işliyor.\n\n"
            "Oyun yönetici olarak çalışıyorsa bu programı da yönetici olarak "
            "başlat."
        )
        self.settings_box.add(self.embed_check)

        self.live_view_button = QPushButton("Canlı görünümü aç", self.settings_box)
        self.live_view_button.setToolTip(
            "Oyunun otomasyona giden görüntüsünü ayrı, boyutlandırılabilir bir "
            "pencerede gösterir."
        )
        self.settings_box.add(self.live_view_button)

    def _connect_ui(self):
        for tab in (self.general_tab, self.attack_tab, self.priest_tab,
                    self.other_tab, self.calibration_tab):
            tab.changed.connect(self._on_changed)
        for header in (self.general_tab.header, self.attack_tab.header,
                       self.priest_tab.heal_header, self.priest_tab.buff_header,
                       self.other_tab.header):
            header.hotkeyChanged.connect(lambda _norm: self._rebuild_bindings())
        for button in (self.other_tab.record_hotkey, self.other_tab.stop_hotkey,
                       self.other_tab.play_hotkey):
            button.keyChanged.connect(lambda _norm: self._rebuild_bindings())
        self.save_button.clicked.connect(self.save_settings)
        self.new_profile_button.clicked.connect(self._new_profile)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        self.capture_title_button.clicked.connect(self._capture_title_delayed)
        self.window_edit.textChanged.connect(self._on_title_edited)
        self.info_tab.testKeyRequested.connect(self._send_test_key)
        self.master_hotkey.keyChanged.connect(lambda _: self._rebuild_bindings())
        self.panic_hotkey.keyChanged.connect(lambda _: self._rebuild_bindings())
        self.on_top_check.toggled.connect(self._on_top_toggled)
        self.overlay_check.toggled.connect(self._on_overlay_toggled)
        self.embed_check.toggled.connect(self._on_embed_toggled)
        self.live_view_button.clicked.connect(self._toggle_live_view)
        self.live_view.visibilityChanged.connect(self._on_live_view_closed)
        self.beep_check.toggled.connect(self._on_beep_toggled)
        self.opacity_slider.valueChanged.connect(self._on_opacity)
        self.tray_check.toggled.connect(lambda _: self._on_changed())

    def _wrap_scroll(self, tab):
        """Sekmeyi kaydırılabilir alana sarar: içerik hiçbir zaman kesilmesin."""
        scroll = QScrollArea(self)
        scroll.setWidget(tab)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scrolls[tab] = scroll
        return scroll

    def _build_tray(self):
        icon = self.style().standardIcon(QStyle.SP_ComputerIcon)
        self.setWindowIcon(icon)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()
        for caption, slot in (
            ("Göster", self._restore_from_tray),
            ("Kompakt mod", lambda: self.set_compact(True)),
            ("Normal görünüm", lambda: self.set_compact(False)),
            ("Master aç/kapa", self._toggle_master),
            ("Çıkış", self._quit_from_tray),
        ):
            action = QAction(caption, self)
            action.triggered.connect(slot)
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()
        self._tray_menu = menu

    def _connect_services(self):
        self.manager.calibrationMissing.connect(self._on_calibration_missing)
        self.manager.moduleStateChanged.connect(self._on_module_state)
        self.manager.moduleSelfDisabled.connect(self._on_module_failed)
        self.manager.masterChanged.connect(self._on_master_changed)
        self.manager.panicChanged.connect(self._on_panic_changed)
        self.hotkeys.hotkeyPressed.connect(self._on_hotkey)
        self.hotkeys.unavailable.connect(
            lambda msg: QMessageBox.warning(self, "Kısayollar", msg)
        )
        self.priest_tab.partyCountChanged.connect(self.party.set_manual_count)
        self.status_reader.resolutionMismatch.connect(self._on_resolution_changed)
        self.death_guard.deathDetected.connect(self._on_death)
        self.death_guard.recovered.connect(self._on_recovered)
        self.window_guard.titleCaptured.connect(self._on_title_captured)
        self.window_guard.hwndChanged.connect(self._on_hwnd_changed)
        self.window_guard.embedStatusChanged.connect(self.live_view.set_status)
        self.recorder.unavailable.connect(
            lambda msg: QMessageBox.warning(self, "Tıklayıcı", msg)
        )

    # ================================================================== master
    def _toggle_master(self):
        if not self.manager.master_on and not self.window_edit.text().strip():
            if self.window_guard.capture_current():
                self._title_autocaptured = True
            elif not self._warned_no_title:
                # Master'a panele tıklayarak basıldıysa ön plandaki pencere
                # bizizdir; kendi başlığımızı oyun sanmıyoruz.
                self._warned_no_title = True
                QMessageBox.information(
                    self, "Oyun penceresi",
                    "Oyun penceresi henüz ayarlanmadı ve otomatik alınamadı "
                    "(bu sırada ön planda bu paneldi).\n\nGenel sekmesinin "
                    "altındaki 'Yakala' düğmesini kullan: bastıktan sonra 3 "
                    "saniye içinde oyuna geç.",
                )
        self.manager.toggle_master()

    def _master_text(self):
        if self.manager.panicking:
            return "MASTER · PANİK"
        if not self.manager.master_on:
            return "MASTER · PASİF"
        if self._active_since is None:
            return "MASTER · AKTİF"
        minutes = int((time.monotonic() - self._active_since) // 60)
        return "MASTER · AKTİF · {} dk".format(minutes)

    def _refresh_master(self):
        on = self.manager.master_on
        self.master_button.setText(self._master_text())
        self.master_button.setObjectName("masterOn" if on else "masterOff")
        self.master_button.style().unpolish(self.master_button)
        self.master_button.style().polish(self.master_button)

    def _on_master_changed(self, value):
        self._active_since = time.monotonic() if value else None
        if not value:
            self.death_guard.reset()
            # Arka plan modunda otomasyon oyunun odağını TUTAR; master kapanınca
            # odak kullanıcının penceresine geri verilir, aksi halde kullanıcı
            # yazmaya devam ettiğinde tuşlar oyuna giderdi.
            self.ctx.input.release_focus()
        self._set_banner("" if value else "Pasif")
        self._refresh_master()

    def _on_panic_changed(self, active):
        if active:
            self.ctx.input.release_focus()      # panikte odak da geri verilir
        self._set_banner("PANİK — her şey durduruldu", RED if active else None)
        if not active:
            self._set_banner("")
        self._refresh_master()

    def _set_banner(self, text, color=None):
        self.uptime_label.setText(text or "")
        self.uptime_label.setVisible(bool(text))
        self.uptime_label.setStyleSheet(
            "color: {}; font-weight: 600;".format(color or MUTED)
        )

    # ================================================================== kısayol
    def _rebuild_bindings(self):
        bindings = {
            "app::master": self.master_hotkey.key(),
            "app::panic": self.panic_hotkey.key(),
            "module::" + MODULE_POT: self.general_tab.header.hotkey_value(),
            "module::" + MODULE_ATTACK: self.attack_tab.header.hotkey_value(),
            "module::" + MODULE_HEAL: self.priest_tab.heal_header.hotkey_value(),
            "module::" + MODULE_BUFF: self.priest_tab.buff_header.hotkey_value(),
            "module::" + MODULE_CLICKER: self.other_tab.header.hotkey_value(),
        }
        bindings.update({
            "clicker::record": self.other_tab.record_hotkey.key(),
            "clicker::stop": self.other_tab.stop_hotkey.key(),
            "clicker::play": self.other_tab.play_hotkey.key(),
        })
        self.hotkeys.set_bindings(bindings)
        self._check_conflicts(bindings)
        self._on_changed()

    def _warn_duplicate_hotkeys(self, bindings):
        """Aynı fiziksel tuş iki kısayola atandıysa yalnızca biri çalışır."""
        seen = {}
        duplicates = []
        for name, hotkey in bindings.items():
            if not hotkey:
                continue
            if hotkey in seen:
                duplicates.append((seen[hotkey], name, hotkey))
            else:
                seen[hotkey] = name
        fresh = [d for d in duplicates if d not in self._warned_conflicts]
        if not fresh or self._loading:
            return
        self._warned_conflicts.update(fresh)
        lines = [
            "{} ile {} aynı tuşa ({}) atanmış.".format(
                first.split("::")[-1], second.split("::")[-1], display_name(key)
            )
            for first, second, key in fresh
        ]
        QMessageBox.warning(
            self, "Kısayol çakışması",
            "\n".join(lines) + "\n\nBu tuşa basıldığında yalnızca biri çalışır.",
        )

    def _check_conflicts(self, bindings):
        self._warn_duplicate_hotkeys(bindings)
        action_keys = set()
        for tab in (self.general_tab, self.attack_tab, self.priest_tab):
            action_keys.update(k for k in tab.action_keys() if k)
        clashes = []
        for name, hotkey in bindings.items():
            if not hotkey:
                continue
            for action_key in action_keys:
                if action_key_conflicts(hotkey, action_key):
                    clashes.append((name, hotkey, action_key))
        fresh = [c for c in clashes if c not in self._warned_conflicts]
        if not fresh or self._loading:
            return
        self._warned_conflicts.update(fresh)
        lines = [
            "{} kısayolu ({}) oyuna gönderilen '{}' tuşuyla aynı.".format(
                name.split("::")[-1], display_name(hotkey), action_key
            )
            for name, hotkey, action_key in fresh
        ]
        QMessageBox.warning(
            self, "Kısayol çakışması",
            "\n".join(lines) + "\n\nEngellenmedi, ama bu tuşa bastığında hem "
            "kısayol çalışır hem de oyuna tuş gider.",
        )

    def _on_hotkey(self, name):
        if name == "app::master":
            self._toggle_master()
            return
        if name == "app::panic":
            self.manager.panic()
            return
        if name.startswith("module::"):
            self._toggle_module_from_hotkey(name.split("::", 1)[1])
            return
        if name == "clicker::record":
            self.other_tab.start_recording()
        elif name == "clicker::stop":
            self.other_tab.stop_all()
        elif name == "clicker::play":
            self.other_tab.start_playback()

    def _toggle_module_from_hotkey(self, module_id):
        module = self.manager.get(module_id)
        if module is None:
            return
        checks = {
            MODULE_POT: self.general_tab.header.check,
            MODULE_ATTACK: self.attack_tab.header.check,
            MODULE_HEAL: self.priest_tab.heal_header.check,
            MODULE_BUFF: self.priest_tab.buff_header.check,
            MODULE_CLICKER: self.other_tab.header.check,
        }
        if module_id in checks:
            checks[module_id].setChecked(not module.enabled)

    # ================================================================== olaylar
    def _on_changed(self):
        if self._loading:
            return
        self.settings.mark_dirty()
        self._update_title()

    def _update_title(self):
        mark = " •" if self.settings.dirty else ""
        self.setWindowTitle("{} — {}{}".format(
            APP_NAME, self.settings.current_profile, mark
        ))

    def _on_title_edited(self, text):
        self.window_guard.set_title(text)
        self._on_changed()

    def _on_title_captured(self, title):
        self.window_edit.blockSignals(True)
        self.window_edit.setText(title)
        self.window_edit.blockSignals(False)
        self.window_guard.set_title(title)
        self._on_changed()

    def _capture_title_delayed(self):
        QMessageBox.information(
            self, "Pencere yakala",
            "Tamam'a bastıktan sonra 3 saniye içinde oyun penceresine geç.",
        )
        QTimer.singleShot(3000, self.window_guard.capture_current)

    def _send_test_key(self):
        """Faz 0 aracı: girdi yolunu oyun olmadan dener."""
        QMessageBox.information(
            self, "Test tuşu",
            "Tamam'a bastıktan sonra 3 saniye içinde Not Defteri gibi bir "
            "pencereye geç. Oraya 'A' harfi düşerse girdi arka ucu ({}) "
            "çalışıyor demektir.".format(self.ctx.input.backend),
        )
        QTimer.singleShot(3000, lambda: self.ctx.input.press_key("A"))

    def _on_opacity(self, value):
        self.setWindowOpacity(max(OPACITY_MIN, int(value)) / 100.0)
        self._on_changed()

    def _on_top_toggled(self, value):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(value))
        self.show()
        self._on_changed()

    def _on_overlay_toggled(self, value):
        self.overlay.setVisible(bool(value))
        self._on_changed()

    # ------------------------------------------------------------- arka plan
    def _on_embed_toggled(self, value):
        self._apply_embed_mode(bool(value))
        self._on_changed()

    def _apply_embed_mode(self, enabled):
        """Tarayıcı modu + pencere takibi + girdi hedefi tek yerden anahtarlanır."""
        if enabled and not self.window_edit.text().strip():
            if not self._loading:
                QMessageBox.information(
                    self, "Arka plan modu",
                    "Önce oyun penceresi başlığını gir veya 'Yakala' ile al.\n"
                    "Arka plan modu takip edilecek pencereyi başlıktan bulur.",
                )
        self.ctx.scanner.set_mode(MODE_WINDOW if enabled else MODE_SCREEN)
        self.window_guard.set_embed_mode(enabled)
        if enabled:
            if self._live_view_wanted:
                self._show_live_view()
        else:
            self.ctx.scanner.set_target_hwnd(None)
            self.ctx.input.set_embed_target(None)
            self.live_view.stop()
            self.live_view.hide()
        self._update_live_view_button()

    def _on_hwnd_changed(self, hwnd):
        """Takip edilen pencere değişti: hem tarayıcı hem girdi aynı HWND'ye bakar."""
        self.ctx.scanner.set_target_hwnd(hwnd)
        self.ctx.input.set_embed_target(hwnd)
        if hwnd and not self._warned_elevation:
            self._check_elevation(hwnd)

    def _check_elevation(self, hwnd):
        """Oyun yönetici, biz değilsek odak devri çalışmaz — bir kez uyar."""
        try:
            from ..services import window_capture

            game_pid = window_capture.window_pid(hwnd)
            if not game_pid:
                return
            if (window_capture.is_process_elevated(game_pid)
                    and not window_capture.is_process_elevated()):
                self._warned_elevation = True
                QMessageBox.warning(
                    self, "Yönetici hakkı gerekiyor",
                    "Oyun YÖNETİCİ olarak çalışıyor, bu program ise normal "
                    "haklarla.\n\nBu durumda Windows, oyuna tuş/tık "
                    "gönderilmesini engeller. Programı yönetici olarak "
                    "yeniden başlat.",
                )
        except Exception:
            pass

    def _toggle_live_view(self):
        if self.live_view.isVisible():
            self._live_view_wanted = False
            self.live_view.stop()
            self.live_view.hide()
        else:
            self._live_view_wanted = True
            self._show_live_view()
        self._update_live_view_button()
        self._on_changed()

    def _show_live_view(self):
        self.live_view.show()
        self.live_view.raise_()
        self.live_view.start()

    def _on_live_view_closed(self, _visible):
        self._live_view_wanted = False
        self._update_live_view_button()

    def _update_live_view_button(self):
        self.live_view_button.setText(
            "Canlı görünümü kapat" if self.live_view.isVisible()
            else "Canlı görünümü aç"
        )

    def _on_beep_toggled(self, value):
        self.ctx.sound.enabled = bool(value)
        self._on_changed()

    def _on_module_state(self, module_id, state, detail):
        self.info_tab.set_module_state(module_id, state, detail)
        if module_id == MODULE_POT:
            self.general_tab.set_state(state)
        elif module_id == MODULE_ATTACK:
            self.attack_tab.set_state(state)
        elif module_id in (MODULE_HEAL, MODULE_BUFF):
            self.priest_tab.set_state(module_id, state)
        elif module_id == MODULE_CLICKER:
            self.other_tab.set_state(state)

    def _on_module_failed(self, module_id, reason):
        self._force_unchecked(module_id)
        QMessageBox.critical(
            self, "Modül durduruldu",
            "{} modülü üst üste hata verdiği için kendini durdurdu.\n\n"
            "Son hata: {}\n\nDiğer modüller çalışmaya devam ediyor.".format(
                MODULE_LABELS.get(module_id, module_id), reason
            ),
        )

    def _force_unchecked(self, module_id):
        if module_id == MODULE_POT:
            self.general_tab.force_unchecked()
        elif module_id == MODULE_ATTACK:
            self.attack_tab.force_unchecked()
        elif module_id in (MODULE_HEAL, MODULE_BUFF):
            self.priest_tab.force_unchecked(module_id)
        elif module_id == MODULE_CLICKER:
            self.other_tab.force_unchecked()

    def _on_calibration_missing(self, module_id, missing):
        self._force_unchecked(module_id)
        if self._loading:
            self._pending_missing.append((module_id, list(missing)))
            return
        names = ", ".join(CALIB_LABELS.get(n, n) for n in missing)
        QMessageBox.warning(
            self, "Kalibrasyon eksik",
            "{} modülü için önce şu kayıtlar gerekli:\n\n{}\n\n"
            "İlgili çerçeveler ekrana getirildi.".format(
                MODULE_LABELS.get(module_id, module_id), names
            ),
        )
        self.tabs.setCurrentWidget(self._scrolls[self.calibration_tab])
        self.calibration_tab.show_frames(missing)

    def _on_resolution_changed(self, saved, current):
        self.manager.set_master(False)
        answer = QMessageBox.question(
            self, "Çözünürlük değişti",
            "Kalibrasyon {}x{} boyutunda yapılmıştı, şu an {}x{}.\n\n"
            "Modüller durduruldu. Kalibrasyonu yeni boyuta göre otomatik "
            "yeniden ölçeklemek ister misin?\n\n"
            "(Sonuç tam oturmazsa Kalibrasyon sekmesinden elle "
            "düzeltebilirsin.)".format(
                saved[0], saved[1], current[0], current[1]),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Yes:
            if self.ctx.calibration.rescale_to_scanner(self.ctx.scanner):
                self.settings.mark_dirty()
                self.calibration_tab.refresh_list()
                self._update_title()
                QMessageBox.information(
                    self, "Yeniden ölçeklendi",
                    "Kalibrasyon yeni boyuta oranlandı. Kalıcı olması için "
                    "Kaydet'e bas.",
                )

    def _on_death(self):
        self._set_banner("ÖLÜM KORUMASI — modüller duraklatıldı", RED)

    def _on_recovered(self):
        self._set_banner("")

    # ================================================================== kompakt
    def set_compact(self, value):
        """Kompakt mod: master düğmesi + köşedeki geri dönüş düğmesi kalır."""
        self._compact = bool(value)
        for widget in (self.chips_row, self.checks_row, self.tabs):
            widget.setVisible(not self._compact)
        if self._compact:
            self.compact_button.setText("⤢")
            self.compact_button.setToolTip("Normal görünüme dön.")
            self.setMinimumSize(0, 0)
            self.resize(240, 64)
        else:
            self.compact_button.setText("⤡")
            self.compact_button.setToolTip(
                "Kompakt mod: yalnızca master düğmesi kalır. Aynı düğmeyle "
                "geri dönersin."
            )
            self.setMinimumWidth(PANEL_WIDTH)
            self.resize(PANEL_WIDTH, PANEL_HEIGHT)

    def mouseDoubleClickEvent(self, event):
        if self._compact:
            self.set_compact(False)
        super().mouseDoubleClickEvent(event)

    # ================================================================== tepsi
    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._restore_from_tray()

    def _restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self):
        self._force_quit = True
        self.close()

    # ================================================================== profil
    def _refresh_profiles(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(self.settings.profiles())
        index = self.profile_combo.findText(self.settings.current_profile)
        if index >= 0:
            self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False)

    def _new_profile(self):
        name, ok = QInputDialog.getText(self, "Yeni profil", "Profil adı:")
        name = (name or "").strip()
        if not ok or not name:
            return
        self.settings.create_profile(name)
        self.settings.current_profile = name
        self._collect_into_settings()
        self._refresh_profiles()
        self._on_changed()

    def _on_profile_selected(self, _index):
        name = self.profile_combo.currentText()
        if not name or name == self.settings.current_profile:
            return
        if self.settings.dirty:
            answer = QMessageBox.question(
                self, "Kaydedilmemiş değişiklik",
                "Mevcut profildeki değişiklikler kaydedilmedi. Önce kaydedilsin mi?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            )
            if answer == QMessageBox.Cancel:
                self._refresh_profiles()
                return
            if answer == QMessageBox.Yes:
                self.save_settings()
        self.settings.current_profile = name
        self.load_settings()

    # ================================================================== ayarlar
    def load_settings(self):
        self._loading = True
        self._pending_missing = []
        try:
            saved_title = self.settings.app_get("game_window_title", "") or ""
            if APP_NAME.lower() in saved_title.lower():
                # Eski sürümde panelin kendi başlığı kaydedilebiliyordu.
                saved_title = ""
            self.window_edit.setText(saved_title)
            self.window_guard.set_title(saved_title)
            self.master_hotkey.set_key(self.settings.app_get("master_hotkey", "f8"))
            self.panic_hotkey.set_key(self.settings.app_get("panic_hotkey", "end"))
            self.on_top_check.setChecked(bool(self.settings.app_get("always_on_top", False)))
            self.beep_check.setChecked(bool(self.settings.app_get("beep_enabled", True)))
            self.tray_check.setChecked(bool(self.settings.app_get("tray_enabled", True)))
            self.overlay_check.setChecked(bool(self.settings.app_get("overlay_enabled", False)))
            self.opacity_slider.set_value(int(self.settings.app_get("window_opacity", 100)))
            self._on_opacity(self.opacity_slider.value())
            self.ctx.sound.enabled = self.beep_check.isChecked()

            self._live_view_wanted = bool(
                self.settings.app_get("live_view_visible", True)
            )
            geometry = self.settings.app_get("live_view_geometry", None)
            if isinstance(geometry, (list, tuple)) and len(geometry) == 4:
                try:
                    self.live_view.setGeometry(*(int(v) for v in geometry))
                except Exception:
                    pass
            embed = bool(self.settings.app_get("embed_mode", False))
            self.embed_check.blockSignals(True)
            self.embed_check.setChecked(embed)
            self.embed_check.blockSignals(False)
            self._apply_embed_mode(embed)

            self.ctx.calibration.load_dict(self.settings.get_section("Calibration"))
            self.calibration_tab.refresh_list()

            self.general_tab.from_dict(self.settings.get_section("General"))
            self.attack_tab.from_dict(self.settings.get_section("Attack"))
            self.priest_tab.from_dict(self.settings.get_section("Priest"))
            self.party.set_manual_count(self.priest_tab.party_count_value())
            self.other_tab.from_dict(self.settings.get_section("Clicker"))
        finally:
            self._loading = False

        self._rebuild_bindings()
        self._apply_saved_ticks()
        self._refresh_profiles()
        self._refresh_master()
        self._set_banner("Pasif")
        self.settings.clear_dirty()
        self._update_title()

        if self._pending_missing:
            names = set()
            for _module_id, missing in self._pending_missing:
                names.update(missing)
            QMessageBox.information(
                self, "Kalibrasyon eksik",
                "Kayıtlı olan bazı modül tikleri açılamadı, çünkü şu "
                "kalibrasyonlar eksik:\n\n{}\n\nKalibrasyon sekmesinden "
                "tamamlayabilirsin.".format(
                    ", ".join(CALIB_LABELS.get(n, n) for n in sorted(names))
                ),
            )
            self._pending_missing = []

    def _apply_saved_ticks(self):
        """Master hep PASİF başlar; modül tikleri hatırlanır."""
        self._loading = True
        try:
            wanted = {
                MODULE_POT: self.general_tab.pending_enabled(),
                MODULE_ATTACK: self.attack_tab.pending_enabled(),
                MODULE_HEAL: self.priest_tab.pending_heal_enabled(),
                MODULE_BUFF: self.priest_tab.pending_buff_enabled(),
                MODULE_CLICKER: self.other_tab.pending_enabled(),
            }
            for module_id, value in wanted.items():
                if value:
                    self.manager.request_enable(module_id, True)
        finally:
            self._loading = False

    def _collect_into_settings(self):
        self.settings.app_set("game_window_title", self.window_edit.text().strip())
        self.settings.app_set("master_hotkey", self.master_hotkey.key())
        self.settings.app_set("panic_hotkey", self.panic_hotkey.key())
        self.settings.app_set("always_on_top", self.on_top_check.isChecked())
        self.settings.app_set("beep_enabled", self.beep_check.isChecked())
        self.settings.app_set("tray_enabled", self.tray_check.isChecked())
        self.settings.app_set("overlay_enabled", self.overlay_check.isChecked())
        self.settings.app_set("window_opacity", self.opacity_slider.value())
        self.settings.app_set("embed_mode", self.embed_check.isChecked())
        self.settings.app_set("live_view_visible", bool(self._live_view_wanted))
        rect = self.live_view.geometry()
        self.settings.app_set(
            "live_view_geometry",
            [rect.x(), rect.y(), rect.width(), rect.height()],
        )
        self.settings.set_section("Calibration", self.ctx.calibration.to_dict())
        self.settings.set_section("General", self.general_tab.to_dict())
        self.settings.set_section("Attack", self.attack_tab.to_dict())
        self.settings.set_section("Priest", self.priest_tab.to_dict())
        self.settings.set_section("Clicker", self.other_tab.to_dict())

    def save_settings(self):
        self._collect_into_settings()
        try:
            self.settings.save()
        except Exception as exc:
            QMessageBox.critical(
                self, "Kaydedilemedi", "Ayarlar yazılamadı:\n{}".format(exc)
            )
            return
        self._refresh_profiles()
        self._update_title()

    # ================================================================== döngü
    def _poll(self):
        snapshot = self.ctx.live.snapshot()
        self._refresh_chips(snapshot)
        self.info_tab.update_values(
            snapshot,
            scanner_backend=self.ctx.scanner.backend,
            window_title=self.window_guard.title(),
            window_focused=self.ctx.state.game_focused.is_set(),
        )
        if self.overlay.isVisible():
            self.overlay.update_values(snapshot)
        self.priest_tab.refresh_buff_timers()
        self._check_panel_overlap()

        if self.manager.master_on and not self.manager.panicking:
            self.master_button.setText(self._master_text())

    def _refresh_chips(self, snapshot):
        hp = snapshot.get("hp_percent")
        low_hp = hp is not None and hp < 40
        self.chip_hp.set_value(
            "—" if hp is None else "%{:.0f}".format(hp),
            RED if low_hp else TEXT,
            RED_SOFT if low_hp else NEUTRAL_SOFT,
        )
        mp = snapshot.get("mp_percent")
        self.chip_mp.set_value(
            "—" if mp is None else "%{:.0f}".format(mp), TEXT, NEUTRAL_SOFT
        )
        target_on = snapshot.get("target_present")
        self.chip_target.set_value(
            "var" if target_on else "yok",
            GREEN if target_on else TEXT,
            GREEN_SOFT if target_on else NEUTRAL_SOFT,
        )
        broken = snapshot.get("rpr_broken")
        self.chip_rpr.set_value(
            "kırık" if broken else "sağlam",
            RED if broken else GREEN,
            RED_SOFT if broken else GREEN_SOFT,
        )

    def _check_panel_overlap(self):
        """Panel kalibre bir barın üzerine gelirse ölçüm bozulur; bir kez uyar."""
        if self._warned_overlap or not self.isVisible():
            return
        if self.ctx.scanner.mode() == MODE_WINDOW:
            # Arka plan modunda görüntü doğrudan oyun penceresinden alınır;
            # panelin üstünü kapatması ölçümü bozamaz.
            return
        saved = [self.ctx.calibration.rect(n)
                 for n in self.ctx.calibration.saved_names()]
        saved = [r for r in saved if r]
        if not saved:
            return
        ratio = self.devicePixelRatioF() or 1.0
        frame = self.frameGeometry()
        px = (frame.x() * ratio, frame.y() * ratio,
              frame.width() * ratio, frame.height() * ratio)
        for rect in saved:
            if (px[0] < rect[0] + rect[2] and rect[0] < px[0] + px[2]
                    and px[1] < rect[1] + rect[3] and rect[1] < px[1] + px[3]):
                self._warned_overlap = True
                QMessageBox.warning(
                    self, "Panel ölçüm alanının üzerinde",
                    "Program penceresi kalibre edilmiş bir barın üzerine geldi. "
                    "Bu haldeyken o bardan yanlış değer okunur.\n\n"
                    "Pencereyi barların dışına taşı (veya kompakt moda geç).",
                )
                return

    # ================================================================== kapanış
    def closeEvent(self, event):
        if getattr(self, "_force_quit", False) is not True and self.tray_check.isChecked():
            event.ignore()
            self.hide()
            self.tray.showMessage(
                APP_NAME, "Program tepside çalışmaya devam ediyor.",
                QSystemTrayIcon.Information, 2000,
            )
            return

        if self.settings.dirty:
            answer = QMessageBox.question(
                self, "Kaydedilmemiş değişiklik",
                "Ayarlarda kaydedilmemiş değişiklikler var. Kaydedilsin mi?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            )
            if answer == QMessageBox.Cancel:
                event.ignore()
                return
            if answer == QMessageBox.Yes:
                self.save_settings()

        self.poll_timer.stop()
        self.calibration_tab.hide_frames()
        self.overlay.close()
        self.live_view.stop()
        self.live_view.close()
        self.recorder.stop()
        self.status_reader.stop()
        self.death_guard.stop()
        self.window_guard.stop()
        self.hotkeys.stop()
        self.manager.stop_all()
        self.ctx.scanner.stop()
        self.tray.hide()
        event.accept()
        app = QApplication.instance()
        if app is not None:
            app.quit()
