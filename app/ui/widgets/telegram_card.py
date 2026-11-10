"""Hızlı Giriş sekmesindeki Telegram kartı: bot token'ı, eşleştirme, bildirimler."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from ..theme import AMBER, GREEN, MUTED, RED
from .card import Card, field_label, hint_label

HOW_TO = (
    "1) Telegram'da <b>@BotFather</b>'a yaz, <b>/newbot</b> komutuyla bot oluştur.<br>"
    "2) Verdiği <b>token</b>'ı aşağıya yapıştırıp <b>Bağlan</b>'a bas.<br>"
    "3) <b>Eşleştir</b>'e bas, çıkan 6 haneli kodu kendi botuna mesaj olarak gönder."
)


class TelegramCard(Card):
    def __init__(self, store, service, parent=None):
        super().__init__("Telegram", parent)
        self.store = store
        self.service = service

        how = QLabel(HOW_TO, self)
        how.setWordWrap(True)
        how.setTextFormat(Qt.RichText)
        how.setObjectName("hint")
        self.add(how)

        self.add(field_label("Bot token", self))
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.token_edit = QLineEdit(self)
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.token_edit.setPlaceholderText("123456789:AA…")
        self.token_edit.setToolTip(
            "BotFather'ın verdiği token. Windows hesabına bağlı olarak şifreli saklanır.")
        self.connect_button = QPushButton("Bağlan", self)
        self.connect_button.setObjectName("primary")
        self.connect_button.setFixedWidth(76)
        row.addWidget(self.token_edit, 1)
        row.addWidget(self.connect_button)
        self.add_layout(row)

        self.status_label = QLabel("Telegram bağlı değil", self)
        self.status_label.setWordWrap(True)
        self.add(self.status_label)

        self.pair_label = QLabel(self)
        self.pair_label.setWordWrap(True)
        self.pair_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.add(self.pair_label)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(6)
        self.pair_button = QPushButton("Eşleştir", self)
        self.unpair_button = QPushButton("Eşleşmeyi kaldır", self)
        self.unpair_button.setObjectName("danger")
        self.test_button = QPushButton("Test mesajı", self)
        buttons.addWidget(self.pair_button, 1)
        buttons.addWidget(self.test_button, 1)
        self.add_layout(buttons)
        self.add(self.unpair_button)

        self.notify_check = QCheckBox("DC / yeniden giriş bildirimlerini gönder", self)
        self.notify_check.setToolTip(
            "Karakter düşünce, OTP ekranı gelince ve zincir durduğunda/başarısız "
            "olduğunda Telegram'a mesaj gelir.")
        self.add(self.notify_check)
        self.add(hint_label(
            "Bota yazabileceğin komutlar: /durum, /log, /durdur, /panik, /yardim. "
            "Yalnız eşleşmiş sohbet dinlenir; başkalarının mesajları yok sayılır.", self))

        # ---------------------------------------------------- kayıtlı ayarlar
        opts = store.options
        self.token_edit.setText(store.get_secret("telegram_token"))
        self.notify_check.setChecked(bool(opts.get("telegram_notify", True)))
        self._chat_name = str(opts.get("telegram_chat_name", ""))

        self.connect_button.clicked.connect(self._connect)
        self.pair_button.clicked.connect(self._pair)
        self.unpair_button.clicked.connect(self._unpair)
        self.test_button.clicked.connect(self._test)
        self.notify_check.toggled.connect(
            lambda v: store.save_options(telegram_notify=bool(v)))
        service.status.connect(self._on_status)
        service.paired.connect(self._on_paired)

        self._refresh_pair()
        if self.token_edit.text():
            service.configure(self.token_edit.text(), opts.get("telegram_chat_id"))

    # ------------------------------------------------------------ olaylar
    def notify_enabled(self) -> bool:
        return self.notify_check.isChecked()

    def _connect(self):
        token = self.token_edit.text().strip()
        if token and ":" not in token:
            self._on_status("Bu bir bot token'ı gibi görünmüyor (ör. 123456:ABC…).", "err")
            return
        try:
            self.store.set_secret("telegram_token", token)
        except Exception as exc:
            self._on_status("Token kaydedilemedi: {}".format(exc), "err")
            return
        self._on_status("Bağlanıyor…" if token else "Telegram bağlı değil", "warn" if token else "idle")
        self.service.configure(token, self.store.options.get("telegram_chat_id"))
        self._refresh_pair()

    def _pair(self):
        if not self.service.running():
            self._on_status("Önce token'ı girip Bağlan'a bas.", "err")
            return
        code = self.service.start_pairing()
        bot = "@" + self.service.bot_username if self.service.bot_username else "botuna"
        self.pair_label.setText(
            "Eşleştirme kodu: <b style='font-size:15px'>{}</b><br>Bu kodu Telegram'da {} "
            "mesaj olarak gönder.".format(code, bot))
        self.pair_label.setStyleSheet("color: {};".format(AMBER))
        try:
            QApplication.clipboard().setText(code)
        except Exception:
            pass

    def _on_paired(self, chat_id, name):
        self._chat_name = name
        self.store.save_options(telegram_chat_id=int(chat_id), telegram_chat_name=name)
        self._refresh_pair()

    def _unpair(self):
        self.service.unpair()
        self.service.cancel_pairing()
        self._chat_name = ""
        self.store.save_options(telegram_chat_id=None, telegram_chat_name="")
        self._refresh_pair()
        if self.service.running():
            self._on_status("Bağlı: @{} · eşleşme bekleniyor".format(
                self.service.bot_username), "warn")

    def _test(self):
        if not self.service.send("👋 Test mesajı: Birleşik KO bağlantısı çalışıyor."):
            self._on_status("Önce bağlan ve eşleştir.", "err")
        else:
            self._on_status("Test mesajı gönderildi.", "ok")

    def _refresh_pair(self):
        paired = bool(self.service.chat_id)
        self.unpair_button.setVisible(paired)
        self.test_button.setEnabled(paired)
        if paired:
            self.pair_label.setText("✓ Eşleşmiş sohbet: <b>{}</b>".format(
                (self._chat_name or str(self.service.chat_id)).replace("<", "&lt;")))
            self.pair_label.setStyleSheet("color: {};".format(GREEN))
        else:
            self.pair_label.setText("Henüz eşleşmiş sohbet yok.")
            self.pair_label.setStyleSheet("color: {};".format(MUTED))

    def _on_status(self, text, kind="idle"):
        color = {"ok": GREEN, "warn": AMBER, "err": RED}.get(kind, MUTED)
        self.status_label.setText(text)
        self.status_label.setStyleSheet("color: {}; font-weight: 600;".format(color))
