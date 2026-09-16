"""profiles.ini okuma/yazma.

Tuzak #4: ConfigParser interpolation=None ve utf-8 zorunlu (JSON içindeki %
isaretleri ve Turkce karakterler için). Tüm değerler JSON olarak saklanir.

Bolum semasi:
    [App]                          -> profilden bağımsız ayarlar
    [Profile_<ad>.<Bolum>]         -> profile ait ayarlar
"""

import configparser
import json
import os

APP_SECTION = "App"
PROFILE_PREFIX = "Profile_"
DEFAULT_PROFILE = "varsayilan"


def _dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(raw: str):
    try:
        return json.loads(raw)
    except Exception:
        return raw


class SettingsManager:
    def __init__(self, path="profiles.ini"):
        self.path = path
        self._parser = configparser.ConfigParser(interpolation=None)
        self._parser.optionxform = str        # anahtar buyuk/kucuk harfi korunur
        self._dirty = False
        self.current_profile = DEFAULT_PROFILE

    # ------------------------------------------------------------------ kirlilik
    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self):
        self._dirty = True

    def clear_dirty(self):
        self._dirty = False

    # ------------------------------------------------------------------ dosya
    def load(self):
        if os.path.exists(self.path):
            try:
                self._parser.read(self.path, encoding="utf-8")
            except Exception:
                self._parser = configparser.ConfigParser(interpolation=None)
                self._parser.optionxform = str
        if not self._parser.has_section(APP_SECTION):
            self._parser.add_section(APP_SECTION)
        last = self.app_get("last_profile", DEFAULT_PROFILE)
        self.current_profile = last if isinstance(last, str) and last else DEFAULT_PROFILE
        self._dirty = False

    def save(self):
        self.app_set("last_profile", self.current_profile)
        directory = os.path.dirname(os.path.abspath(self.path))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            self._parser.write(handle)
        self._dirty = False

    # ------------------------------------------------------------------ App
    def app_get(self, key, default=None):
        if not self._parser.has_option(APP_SECTION, key):
            return default
        return _loads(self._parser.get(APP_SECTION, key))

    def app_set(self, key, value):
        if not self._parser.has_section(APP_SECTION):
            self._parser.add_section(APP_SECTION)
        raw = _dumps(value)
        if self._parser.has_option(APP_SECTION, key) and self._parser.get(APP_SECTION, key) == raw:
            return
        self._parser.set(APP_SECTION, key, raw)
        self._dirty = True

    # ------------------------------------------------------------------ profil
    def profiles(self):
        names = set()
        for section in self._parser.sections():
            if section.startswith(PROFILE_PREFIX):
                body = section[len(PROFILE_PREFIX):]
                names.add(body.split(".", 1)[0])
        names.add(DEFAULT_PROFILE)
        return sorted(names)

    def _section_name(self, section, profile=None):
        return f"{PROFILE_PREFIX}{profile or self.current_profile}.{section}"

    def get_section(self, section, profile=None) -> dict:
        name = self._section_name(section, profile)
        if not self._parser.has_section(name):
            return {}
        return {key: _loads(raw) for key, raw in self._parser.items(name)}

    def set_section(self, section, values: dict, profile=None):
        name = self._section_name(section, profile)
        if not self._parser.has_section(name):
            self._parser.add_section(name)
            self._dirty = True
        for key, value in (values or {}).items():
            raw = _dumps(value)
            if self._parser.has_option(name, key) and self._parser.get(name, key) == raw:
                continue
            self._parser.set(name, key, raw)
            self._dirty = True

    def get_value(self, section, key, default=None, profile=None):
        return self.get_section(section, profile).get(key, default)

    def delete_profile(self, name):
        if name == DEFAULT_PROFILE:
            return False
        prefix = f"{PROFILE_PREFIX}{name}."
        removed = False
        for section in list(self._parser.sections()):
            if section.startswith(prefix):
                self._parser.remove_section(section)
                removed = True
        if removed:
            self._dirty = True
        if self.current_profile == name:
            self.current_profile = DEFAULT_PROFILE
        return removed

    def create_profile(self, name):
        name = (name or "").strip()
        if not name:
            return False
        section = f"{PROFILE_PREFIX}{name}.App"
        if not self._parser.has_section(section):
            self._parser.add_section(section)
            self._dirty = True
        return True

    def profile_exists(self, name) -> bool:
        prefix = f"{PROFILE_PREFIX}{name}."
        return any(s.startswith(prefix) for s in self._parser.sections())
