"""Hızlı giriş sekmesi: hesabı kaydet, tek tuşla oyuna giriş yap.

Akış (LoginTyper): oyun öne alınır → kullanıcı adı insansı yazılır → ~1 sn →
TAB → şifre insansı yazılır → ~1 sn → ENTER.

Hedef pencere: Genel sekmesindeki "Oyun penceresi" başlığı bulunursa o öne
alınır. Bulunamazsa 3 sn geri sayım yapılır; o sürede oyuna geçmen beklenir.
Giriş kısayolu ise o an ÖNDE olan pencereye yazar (oyundayken bas).
"""

import os

from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...services import window_capture
from ...services.login_typer import LoginTyper, untypable_chars
from ..theme import AMBER, CARD_SPACING, GREEN, MUTED, RED
from ..widgets.card import Card, field_label, hint_label
from ..widgets.common import HotkeyButton

COUNTDOWN_S = 3


class LoginTab(QWidget):
    hotkeyChanged = pyqtSignal(str)

    def __init__(self, store, input_service, app_state, hotkey_service,
                 title_provider, dc_guard=None, parent=None):
        super().__init__(parent)
        self.store = store
        self.guard = dc_guard
        self.store.load()          # DC kartı kayıtlı seçenekleri kurulurken okur
        self._title_provider = title_provider
        self.typer = LoginTyper(input_service, app_state, self)
        self._countdown = 0
        self._count_timer = QTimer(self)
        self._count_timer.setInterval(1000)
        self._count_timer.timeout.connect(self._tick)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(CARD_SPACING + 1)

        # ---------------------------------------------------------- hesap
        account = Card("Hesap", self)
        account.add(field_label("Kullanıcı adı", account))
        self.user_edit = QLineEdit(account)
        self.user_edit.setPlaceholderText("oyun hesabı kullanıcı adı")
        account.add(self.user_edit)

        account.add(field_label("Şifre", account))
        pass_row = QHBoxLayout()
        pass_row.setContentsMargins(0, 0, 0, 0)
        pass_row.setSpacing(6)
        self.pass_edit = QLineEdit(account)
        self.pass_edit.setEchoMode(QLineEdit.Password)
        self.pass_edit.setPlaceholderText("şifre")
        self.show_button = QPushButton("Göster", account)
        self.show_button.setCheckable(True)
        self.show_button.setFixedWidth(70)
        self.show_button.toggled.connect(self._toggle_echo)
        pass_row.addWidget(self.pass_edit, 1)
        pass_row.addWidget(self.show_button)
        account.add_layout(pass_row)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(6)
        self.save_button = QPushButton("Kaydet", account)
        self.save_button.setObjectName("primary")
        self.clear_button = QPushButton("Sil", account)
        self.clear_button.setObjectName("danger")
        self.clear_button.setFixedWidth(70)
        buttons.addWidget(self.save_button, 1)
        buttons.addWidget(self.clear_button)
        account.add_layout(buttons)

        self.saved_label = QLabel(account)
        self.saved_label.setWordWrap(True)
        account.add(self.saved_label)
        account.add(hint_label(
            "Şifre bu bilgisayarda Windows hesabına bağlı olarak şifrelenir "
            "(DPAPI); dosya başka bilgisayara kopyalansa bile çözülemez.",
            account,
        ))
        root.addWidget(account)

        # ---------------------------------------------------------- giriş
        action = Card("Giriş", self)
        self.login_button = QPushButton("GİRİŞ YAP", action)
        self.login_button.setObjectName("go")
        self.login_button.setCursor(Qt.PointingHandCursor)
        action.add(self.login_button)

        self.cancel_button = QPushButton("İptal", action)
        self.cancel_button.setVisible(False)
        action.add(self.cancel_button)

        self.status_label = QLabel("Hazır", action)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        action.add(self.status_label)

        action.add_divider()
        self.hotkey_button = HotkeyButton(
            "Giriş kısayolu", hotkey_service, "app::login", action
        )
        self.hotkey_button.setToolTip(
            "Oyunun giriş ekranındayken bu tuşa bas: kayıtlı hesap o an öndeki "
            "pencereye yazılır."
        )
        action.add(self.hotkey_button)
        action.add(hint_label(
            "Giriş ekranında imleç KULLANICI ADI kutusunda olmalı. Sıra: "
            "kullanıcı adı → 1 sn → TAB → şifre → 1 sn → ENTER. Yazarken "
            "başka pencereye geçersen ya da panik tuşuna basarsan anında durur.",
            action,
        ))
        root.addWidget(action)
        if dc_guard is not None:
            root.addWidget(self._build_dc_card())
        self._root = root
        root.addStretch(1)

        self.save_button.clicked.connect(self._save)
        self.clear_button.clicked.connect(self._clear)
        self.login_button.clicked.connect(self.login_from_panel)
        self.cancel_button.clicked.connect(self._cancel)
        self.hotkey_button.keyChanged.connect(self._on_hotkey)
        self.typer.status.connect(self._set_status)
        self.typer.finished.connect(self._on_finished)

        self._load()

    def add_card(self, widget):
        """Sondaki boşluktan ÖNCE kart ekler (ana pencere Telegram kartını koyar)."""
        self._root.insertWidget(self._root.count() - 1, widget)

    def recent_log(self, count=10):
        if not hasattr(self, "dc_log"):
            return []
        total = self.dc_log.count()
        return [self.dc_log.item(i).text() for i in range(max(0, total - count), total)]

    def dc_status_text(self) -> str:
        return self.dc_status.text() if hasattr(self, "dc_status") else ""

    # ------------------------------------------------------------------ DC
    def _build_dc_card(self):
        card = Card("DC koruması", self)
        self.dc_alarm_check = QCheckBox("DC alarmı", card)
        self.dc_alarm_check.setToolTip(
            "Karakter oyundan düşünce alarm çalar.\n\n"
            "Ekranın ortasındaki 'Disconnected from server' çerçevesi "
            "algılanır, log'a yazılır, master kapatılır ve çerçevedeki "
            "Confirm düğmesine basılır. Önce son bilinen konuma tıklanır; "
            "10 sn sonra çerçeve hâlâ duruyorsa düğme ekranda aranıp tekrar "
            "tıklanır."
        )
        self.relogin_check = QCheckBox("Yeniden gir", card)
        self.relogin_check.setToolTip(
            "Karakter düşünce otomatik yeniden giriş:\n"
            "Confirm → oyunun kapanması 10 sn beklenir → Launcher açılır → "
            "10 sn → START → oyunun açılması 1 dk beklenir → ID kutusuna "
            "tıklanır → hızlı giriş (ID, TAB, şifre, ENTER) → OTP ekranı "
            "gelince 'bip bip' çalar ve bekler.\n\n"
            "Program YÖNETİCİ olarak çalışmalıdır."
        )
        checks = QHBoxLayout()
        checks.setContentsMargins(0, 0, 0, 0)
        checks.setSpacing(16)
        checks.addWidget(self.dc_alarm_check)
        checks.addWidget(self.relogin_check)
        checks.addStretch(1)
        card.add_layout(checks)

        card.add(field_label("Launcher dosyası", card))
        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(6)
        self.launcher_edit = QLineEdit(card)
        self.launcher_edit.setPlaceholderText("Launcher.exe yolu")
        self.launcher_edit.setToolTip("Yeniden girişte açılacak oyun launcher'ı.")
        self.launcher_browse = QPushButton("Seç…", card)
        self.launcher_browse.setFixedWidth(64)
        path_row.addWidget(self.launcher_edit, 1)
        path_row.addWidget(self.launcher_browse)
        card.add_layout(path_row)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(6)
        self.relogin_now_button = QPushButton("Yeniden girişi şimdi dene", card)
        self.relogin_now_button.setToolTip(
            "DC beklemeden zinciri launcher adımından başlatır (test için). "
            "Oyun açıksa önce kapanması beklenir; kapanmazsa iptal edilir."
        )
        self.dc_cancel_button = QPushButton("Durdur", card)
        self.dc_cancel_button.setObjectName("danger")
        self.dc_cancel_button.setFixedWidth(70)
        self.dc_cancel_button.setEnabled(False)
        buttons.addWidget(self.relogin_now_button, 1)
        buttons.addWidget(self.dc_cancel_button)
        card.add_layout(buttons)

        self.dc_status = QLabel("İzleme kapalı", card)
        self.dc_status.setWordWrap(True)
        card.add(self.dc_status)

        card.add(field_label("Log", card))
        self.dc_log = QListWidget(card)
        self.dc_log.setMinimumHeight(110)
        self.dc_log.setWordWrap(True)
        card.add(self.dc_log)
        card.add(hint_label(
            "Log ayrıca program klasöründeki dc_log.txt dosyasına yazılır.", card))

        opts = self.store.options
        self.dc_alarm_check.setChecked(bool(opts.get("dc_alarm", False)))
        self.relogin_check.setChecked(bool(opts.get("relogin", False)))
        self.launcher_edit.setText(str(opts.get("launcher_path", "")))
        self._push_dc_options()
        self._refresh_dc_idle()

        self.dc_alarm_check.toggled.connect(self._on_dc_option)
        self.relogin_check.toggled.connect(self._on_dc_option)
        self.launcher_edit.editingFinished.connect(self._on_dc_option)
        self.launcher_browse.clicked.connect(self._browse_launcher)
        self.relogin_now_button.clicked.connect(self._relogin_now)
        self.dc_cancel_button.clicked.connect(self.guard.cancel)
        self.guard.logLine.connect(self._append_log)
        self.guard.status.connect(self._on_dc_status)
        self.guard.busyChanged.connect(self._on_dc_busy)
        self.guard.optionsChanged.connect(self._on_guard_options)
        return card

    def _push_dc_options(self):
        pos = self.store.options.get("confirm_pos")
        self.guard.set_options(
            self.dc_alarm_check.isChecked(), self.relogin_check.isChecked(),
            self.launcher_edit.text().strip(),
            tuple(pos) if isinstance(pos, (list, tuple)) and len(pos) == 2 else None,
        )

    def _on_dc_option(self, *_):
        self._push_dc_options()
        try:
            self.store.save_options(
                dc_alarm=self.dc_alarm_check.isChecked(),
                relogin=self.relogin_check.isChecked(),
                launcher_path=self.launcher_edit.text().strip(),
            )
        except Exception as exc:
            self._on_dc_status("Ayar kaydedilemedi: {}".format(exc), "err")
            return
        if self.guard.busy():
            return
        if self.relogin_check.isChecked():
            problems = []
            if not self.store.has_account():
                problems.append("kayıtlı hesap yok")
            path = self.launcher_edit.text().strip()
            if not path or not os.path.isfile(path):
                problems.append("Launcher dosyası seçilmedi / bulunamadı")
            if problems:
                self._on_dc_status(
                    "Yeniden gir için: " + ", ".join(problems) + ".", "err")
                return
        self._refresh_dc_idle()

    def _refresh_dc_idle(self):
        if self.dc_alarm_check.isChecked() or self.relogin_check.isChecked():
            self._on_dc_status("İzleniyor — DC olursa: {}.".format(
                "yeniden girilecek" if self.relogin_check.isChecked()
                else "alarm + Confirm"), "ok")
        else:
            self._on_dc_status("İzleme kapalı", "idle")

    def _browse_launcher(self):
        start = os.path.dirname(self.launcher_edit.text().strip()) or ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Launcher'ı seç", start, "Programlar (*.exe);;Tüm dosyalar (*)")
        if path:
            self.launcher_edit.setText(os.path.normpath(path))
            self._on_dc_option()

    def _relogin_now(self):
        if not self.store.has_account():
            self._on_dc_status("Önce hesabı kaydet.", "err")
            return
        path = self.launcher_edit.text().strip()
        if not path or not os.path.isfile(path):
            self._on_dc_status("Önce Launcher dosyasını seç.", "err")
            return
        self._push_dc_options()
        self.guard.relogin_now()

    def _append_log(self, line):
        self.dc_log.addItem(line)
        while self.dc_log.count() > 200:
            self.dc_log.takeItem(0)
        self.dc_log.scrollToBottom()

    def _on_dc_status(self, text, kind="idle"):
        color = {"ok": GREEN, "warn": AMBER, "err": RED}.get(kind, MUTED)
        self.dc_status.setText(text)
        self.dc_status.setStyleSheet("color: {}; font-weight: 600;".format(color))

    def _on_dc_busy(self, busy):
        self.dc_cancel_button.setEnabled(busy)
        self.relogin_now_button.setEnabled(not busy)

    def _on_guard_options(self, values):
        try:
            self.store.save_options(**values)
        except Exception:
            pass

    # ------------------------------------------------------------------ veri
    def _load(self):
        self.store.load()
        self.user_edit.setText(self.store.username)
        self.pass_edit.setText(self.store.password)
        self.hotkey_button.set_key(self.store.hotkey)
        if self.store.error:
            self._set_status(self.store.error, RED)
        self._refresh_saved()

    def hotkey(self) -> str:
        return self.hotkey_button.key()

    def _refresh_saved(self):
        if self.store.has_account():
            self.saved_label.setText("✓ Kayıtlı hesap: <b>{}</b>".format(
                self.store.username.replace("<", "&lt;")))
            self.saved_label.setStyleSheet("color: {};".format(GREEN))
        else:
            self.saved_label.setText("Henüz kayıtlı hesap yok.")
            self.saved_label.setStyleSheet("color: {};".format(MUTED))

    def _toggle_echo(self, show):
        self.pass_edit.setEchoMode(QLineEdit.Normal if show else QLineEdit.Password)
        self.show_button.setText("Gizle" if show else "Göster")

    def _save(self):
        user = self.user_edit.text().strip()
        password = self.pass_edit.text()
        if not user or not password:
            QMessageBox.warning(self, "Hızlı giriş", "Kullanıcı adı ve şifre boş olamaz.")
            return
        bad = untypable_chars(user + password)
        if bad:
            QMessageBox.warning(
                self, "Hızlı giriş",
                "Şu karakterler mevcut klavye düzeninde tuşla yazılamıyor:\n\n"
                "{}\n\nKayıt yapıldı ama giriş bu haliyle başarısız olur.".format(
                    " ".join(bad)),
            )
        try:
            self.store.save(user, password, self.hotkey())
        except Exception as exc:
            QMessageBox.critical(self, "Kaydedilemedi", str(exc))
            return
        self._refresh_saved()
        self._set_status("Hesap kaydedildi.", GREEN)

    def _clear(self):
        if QMessageBox.question(
            self, "Hesabı sil", "Kayıtlı kullanıcı adı ve şifre silinsin mi?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        hotkey = self.hotkey()
        try:
            self.store.clear()
            if hotkey:
                self.store.save_hotkey(hotkey)
        except Exception as exc:
            QMessageBox.critical(self, "Silinemedi", str(exc))
            return
        self.user_edit.clear()
        self.pass_edit.clear()
        self._refresh_saved()
        self._set_status("Hesap silindi.", MUTED)

    def _on_hotkey(self, norm):
        try:
            self.store.save_hotkey(norm)
        except Exception:
            pass
        self.hotkeyChanged.emit(norm)

    # ------------------------------------------------------------------ giriş
    def _ready(self) -> bool:
        if self.typer.busy() or self._count_timer.isActive():
            return False
        if not self.store.has_account():
            self._set_status("Önce hesabı kaydet.", RED)
            return False
        return True

    def login_from_panel(self):
        """Panel düğmesi: oyun penceresi bulunursa öne alınır, yoksa geri sayım."""
        if not self._ready():
            return
        hwnd = window_capture.find_game_window(
            self._title_provider() or "", own_pid=os.getpid()
        )
        if hwnd:
            self._start(hwnd)
            return
        self._countdown = COUNTDOWN_S
        self._set_status(
            "Oyun penceresi bulunamadı. {} sn içinde oyuna geç…".format(self._countdown),
            AMBER,
        )
        self._set_busy(True)
        self._count_timer.start()

    def login_from_hotkey(self):
        """Kısayol: o an ÖNDE olan pencere hedeftir (kendi panelimiz hariç)."""
        if not self._ready():
            return
        hwnd = window_capture.foreground_window()
        if not hwnd or window_capture.window_pid(hwnd) == os.getpid():
            self._set_status("Kısayola oyun öndeyken bas.", RED)
            return
        self._start(hwnd)

    def _tick(self):
        self._countdown -= 1
        if self._countdown > 0:
            self._set_status("{} sn içinde oyuna geç…".format(self._countdown), AMBER)
            return
        self._count_timer.stop()
        hwnd = window_capture.foreground_window()
        if not hwnd or window_capture.window_pid(hwnd) == os.getpid():
            self._set_busy(False)
            self._set_status("Oyuna geçilmedi — giriş iptal.", RED)
            return
        self._start(hwnd)

    def _start(self, hwnd):
        self._set_busy(True)
        self._set_status("Başlıyor…", AMBER)
        if not self.typer.start(self.store.username, self.store.password, hwnd):
            self._set_busy(False)

    def _cancel(self):
        if self._count_timer.isActive():
            self._count_timer.stop()
            self._set_busy(False)
            self._set_status("İptal edildi.", MUTED)
            return
        self.typer.cancel()

    def _on_finished(self, ok, message):
        self._set_busy(False)
        self._set_status(message, GREEN if ok else RED)

    def _set_busy(self, busy):
        self.login_button.setEnabled(not busy)
        self.login_button.setText("YAZILIYOR…" if busy else "GİRİŞ YAP")
        self.cancel_button.setVisible(busy)

    def _set_status(self, text, color=None):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            "color: {}; font-weight: 600;".format(color or MUTED)
        )

    def shutdown(self):
        self._count_timer.stop()
        self.typer.cancel()
        if self.guard is not None:
            self.guard.stop()
