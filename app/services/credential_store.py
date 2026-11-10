"""Hızlı giriş hesap bilgileri: şifre Windows DPAPI ile şifrelenerek saklanır.

Neden ayrı dosya: profiles.ini depoya da giriyor; şifrenin orada (şifreli
bile olsa) durmasını istemiyoruz. `hizli_giris.json` .gitignore'dadır.

DPAPI (CryptProtectData) veriyi o anki WINDOWS KULLANICISINA bağlar: dosya
başka bir bilgisayara/kullanıcıya kopyalanırsa şifre çözülemez. Anahtar
yönetimi gerekmez, ek paket gerekmez (pywin32 zaten bağımlılık).
"""

import base64
import json
import os

try:
    import win32crypt

    DPAPI_AVAILABLE = True
except Exception:                                    # pragma: no cover
    DPAPI_AVAILABLE = False

FILE_NAME = "hizli_giris.json"
_ENTROPY = b"BirlesikKO.hizli-giris.v1"


def _protect(text: str) -> str:
    if not text:
        return ""
    blob = win32crypt.CryptProtectData(
        text.encode("utf-8"), "hizli-giris", _ENTROPY, None, None, 0
    )
    return base64.b64encode(blob).decode("ascii")


def _unprotect(data: str) -> str:
    if not data:
        return ""
    raw = base64.b64decode(data.encode("ascii"))
    _desc, plain = win32crypt.CryptUnprotectData(raw, _ENTROPY, None, None, 0)
    return plain.decode("utf-8")


class CredentialStore:
    """Tek hesap: kullanıcı adı düz, şifre DPAPI ile şifreli."""

    def __init__(self, folder: str):
        self.path = os.path.join(folder or ".", FILE_NAME)
        self.username = ""
        self.password = ""
        self.hotkey = ""
        self.options = {}          # DC koruması: tikler, launcher yolu, Confirm konumu
        self.error = ""

    @property
    def available(self) -> bool:
        return DPAPI_AVAILABLE

    def has_account(self) -> bool:
        return bool(self.username and self.password)

    def load(self) -> bool:
        self.error = ""
        if not os.path.exists(self.path):
            return False
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self.username = str(data.get("username", ""))
            self.hotkey = str(data.get("hotkey", ""))
            options = data.get("options", {})
            self.options = options if isinstance(options, dict) else {}
            self.password = _unprotect(data.get("password", "")) if DPAPI_AVAILABLE else ""
            return True
        except Exception as exc:
            # Başka kullanıcıdan kopyalanmış dosya vb.: şifre çözülemez.
            self.password = ""
            self.error = "Kayıtlı şifre okunamadı ({}). Yeniden kaydet.".format(exc)
            return False

    def save(self, username: str, password: str, hotkey: str = None):
        if not DPAPI_AVAILABLE:
            raise RuntimeError("Windows şifreleme (DPAPI) kullanılamıyor.")
        self.username = (username or "").strip()
        self.password = password or ""
        if hotkey is not None:
            self.hotkey = hotkey or ""
        payload = {
            "username": self.username,
            "password": _protect(self.password),
            "hotkey": self.hotkey,
            "options": self.options,
        }
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def save_hotkey(self, hotkey: str):
        """Yalnız kısayolu güncelle (şifreye dokunmadan)."""
        self.hotkey = hotkey or ""
        self.save(self.username, self.password, self.hotkey)

    def save_options(self, **values):
        """DC koruması ayarlarını günceller (şifreye dokunmadan)."""
        self.options.update(values)
        self.save(self.username, self.password, self.hotkey)

    def set_secret(self, key, value):
        """Gizli değeri (ör. Telegram token) DPAPI ile şifreleyip options'a yazar."""
        if not DPAPI_AVAILABLE:
            raise RuntimeError("Windows şifreleme (DPAPI) kullanılamıyor.")
        self.save_options(**{key + "_enc": _protect(value or "")})

    def get_secret(self, key) -> str:
        data = self.options.get(key + "_enc", "")
        if not data or not DPAPI_AVAILABLE:
            return ""
        try:
            return _unprotect(data)
        except Exception:
            return ""

    def clear(self):
        """Hesabı siler; kısayol ve DC ayarları korunur."""
        self.username = ""
        self.password = ""
        if os.path.exists(self.path):
            os.remove(self.path)
        if self.hotkey or self.options:
            self.save("", "", self.hotkey)
