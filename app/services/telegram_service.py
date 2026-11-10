"""Telegram botu ile iki yönlü iletişim (BotFather'dan alınan token ile).

  * GÖNDERİM: bildirimler (DC, OTP bekleniyor, hata...) sıraya alınır, ayrı bir
    thread gönderir; ağ yoksa birkaç kez yeniden dener, arayüz hiç donmaz.
  * ALIM: getUpdates uzun yoklama (25 sn). Gelen komutlar sinyalle GUI
    thread'ine iletilir.
  * EŞLEŞTİRME: Bot herkese açık bir adrestir; yabancı biri bota yazabilir.
    Bu yüzden yalnız EŞLEŞMİŞ sohbet dinlenir. Eşleştirme için arayüz tek
    kullanımlık 6 haneli bir kod üretir; kullanıcı bu kodu bota yazınca o
    sohbet kaydedilir. Başka sohbetlerden gelen her şey yok sayılır.

Açılışta birikmiş eski mesajlar ATLANIR: program kapalıyken yazılmış bir
"/panik" saatler sonra beklenmedik anda çalışmasın.

Ek paket gerekmez (urllib). API adresi testler için değiştirilebilir.
"""

import json
import queue
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from PyQt5.QtCore import QObject, pyqtSignal

API_BASE = "https://api.telegram.org"
POLL_TIMEOUT_S = 25
SEND_RETRIES = 3
MAX_TEXT = 4000                 # Telegram sınırı 4096


class TelegramError(Exception):
    def __init__(self, message, code=None, retry_after=None):
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after


class TelegramService(QObject):
    status = pyqtSignal(str, str)           # (metin, tür: ok/warn/err/idle)
    botIdentified = pyqtSignal(str)         # @kullanıcıadı
    paired = pyqtSignal(int, str)           # (chat_id, görünen ad)
    commandReceived = pyqtSignal(str, str)  # ("/durum", "argümanlar")
    textReceived = pyqtSignal(str)          # komut olmayan düz metin (ileride: OTP vb.)

    def __init__(self, api_base=API_BASE, parent=None):
        super().__init__(parent)
        self._api_base = api_base.rstrip("/")
        self._token = ""
        self._chat_id = None
        self._pair_code = None
        self._stop = threading.Event()
        self._poll_thread = None
        self._send_thread = None
        self._outbox = queue.Queue()
        self.bot_username = ""

    # ------------------------------------------------------------ yapılandırma
    @property
    def chat_id(self):
        return self._chat_id

    def running(self) -> bool:
        return self._poll_thread is not None and self._poll_thread.is_alive()

    def configure(self, token, chat_id=None):
        """Token/sohbet değişti: yoklamayı yeniden başlatır (boş token = kapat)."""
        self.stop()
        self._token = (token or "").strip()
        self._chat_id = int(chat_id) if chat_id else None
        self.bot_username = ""
        if not self._token:
            self.status.emit("Telegram bağlı değil", "idle")
            return
        self._stop.clear()
        self._poll_thread = threading.Thread(target=self._poll_loop, name="tg-poll", daemon=True)
        self._send_thread = threading.Thread(target=self._send_loop, name="tg-send", daemon=True)
        self._poll_thread.start()
        self._send_thread.start()

    def stop(self):
        self._stop.set()
        self._outbox.put(None)                   # gönderici uyansın
        for thread in (self._poll_thread, self._send_thread):
            if thread is not None:
                thread.join(timeout=1.0)
        self._poll_thread = self._send_thread = None
        self._outbox = queue.Queue()

    def start_pairing(self) -> str:
        self._pair_code = "{:06d}".format(random.SystemRandom().randint(0, 999999))
        return self._pair_code

    def cancel_pairing(self):
        self._pair_code = None

    def unpair(self):
        self._chat_id = None

    # ------------------------------------------------------------ gönderim
    def send(self, text, chat_id=None) -> bool:
        """Mesajı sıraya alır. Eşleşmiş sohbet yoksa False."""
        target = chat_id or self._chat_id
        if not self._token or not target:
            return False
        text = str(text)
        if len(text) > MAX_TEXT:
            text = text[:MAX_TEXT - 1] + "…"
        self._outbox.put((int(target), text))
        return True

    def _send_loop(self):
        while not self._stop.is_set():
            item = self._outbox.get()
            if item is None:
                continue
            chat_id, text = item
            for attempt in range(SEND_RETRIES):
                if self._stop.is_set():
                    return
                try:
                    self._call("sendMessage", {"chat_id": chat_id, "text": text,
                                               "disable_web_page_preview": True})
                    break
                except TelegramError as exc:
                    if exc.retry_after:
                        self._stop.wait(float(exc.retry_after))
                    elif exc.code in (400, 401, 403, 404):
                        self.status.emit("Mesaj gönderilemedi: {}".format(exc), "err")
                        break
                    else:
                        self._stop.wait(2.0 * (attempt + 1))
                except Exception:
                    self._stop.wait(2.0 * (attempt + 1))

    # ------------------------------------------------------------ alım
    def _poll_loop(self):
        offset = None
        identified = False
        backoff = 2.0
        while not self._stop.is_set():
            try:
                if not identified:
                    me = self._call("getMe", {})
                    self.bot_username = me.get("username", "")
                    self.botIdentified.emit(self.bot_username)
                    # Birikmiş eski güncellemeleri atla
                    old = self._call("getUpdates", {"offset": -1, "timeout": 0})
                    if old:
                        offset = old[-1]["update_id"] + 1
                    identified = True
                    self._emit_connected()
                params = {"timeout": POLL_TIMEOUT_S, "allowed_updates": ["message"]}
                if offset is not None:
                    params["offset"] = offset
                updates = self._call("getUpdates", params, timeout=POLL_TIMEOUT_S + 10)
                backoff = 2.0
                for update in updates or []:
                    offset = update["update_id"] + 1
                    self._handle_update(update)
            except TelegramError as exc:
                if exc.code == 401:
                    self.status.emit("Token geçersiz — BotFather'dan aldığın token'ı kontrol et.", "err")
                    return
                if exc.code == 409:
                    self.status.emit("Bu bot başka bir yerde de dinleniyor (409). "
                                     "Programın ikinci kopyasını kapat.", "err")
                    self._stop.wait(10.0)
                    continue
                self.status.emit("Telegram hatası: {} — yeniden deneniyor".format(exc), "warn")
                self._stop.wait(backoff)
                backoff = min(60.0, backoff * 2)
            except Exception as exc:
                self.status.emit("Telegram'a ulaşılamıyor ({}) — yeniden deneniyor".format(
                    type(exc).__name__), "warn")
                self._stop.wait(backoff)
                backoff = min(60.0, backoff * 2)

    def _emit_connected(self):
        if self._chat_id:
            self.status.emit("Bağlı: @{} · eşleşmiş".format(self.bot_username), "ok")
        else:
            self.status.emit("Bağlı: @{} · eşleşme bekleniyor".format(self.bot_username), "warn")

    def _handle_update(self, update):
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = (message.get("text") or "").strip()
        if not chat_id or not text:
            return
        if self._pair_code and self._pair_code in text.replace(" ", ""):
            self._pair_code = None
            self._chat_id = int(chat_id)
            name = (chat.get("first_name") or chat.get("title")
                    or chat.get("username") or str(chat_id))
            self.paired.emit(int(chat_id), name)
            self._emit_connected()
            self.send("✅ Eşleşti! Artık bildirimler buraya gelecek.\n/yardim yazarak "
                      "komutları görebilirsin.", chat_id)
            return
        if int(chat_id) != self._chat_id:
            return                       # eşleşmemiş sohbet: yok say
        if text.startswith("/"):
            head, _, args = text.partition(" ")
            command = head.split("@", 1)[0].lower()      # /durum@BotAdi → /durum
            self.commandReceived.emit(command, args.strip())
        else:
            self.textReceived.emit(text)

    # ------------------------------------------------------------ HTTP
    def _call(self, method, params, timeout=15):
        url = "{}/bot{}/{}".format(self._api_base, self._token, method)
        body = json.dumps(params).encode("utf-8")
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8"))
            except Exception:
                raise TelegramError("HTTP {}".format(exc.code), exc.code)
        if not payload.get("ok"):
            params_ = payload.get("parameters") or {}
            raise TelegramError(payload.get("description", "bilinmeyen hata"),
                                payload.get("error_code"), params_.get("retry_after"))
        return payload.get("result")
