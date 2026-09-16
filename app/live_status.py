"""Kilitli, RAM içi durum tablosu.

Loglama yok (performans kararı). Worker thread'ler buraya yazar, UI 250-500 ms
QTimer ile okur. Yalnız durum GEÇİŞLERİ ayrıca sinyalle bildirilir.
"""

import threading


class LiveStatus:
    def __init__(self):
        self._lock = threading.Lock()
        self._data = {
            "hp_percent": None,
            "hp_present": False,
            # HP barının renk durumu — YALNIZ bilgi amaçlı, hiçbir karara bağlı
            # değil. None = geometri yok / okunamadı.
            "hp_state": None,
            "hp_state_label": "",
            "mp_percent": None,
            "target_present": False,
            "target_percent": 0.0,
            "rpr_broken": False,
            "rpr_ratio": None,
            "party": [],              # [{"index":0,"percent":97.0,"present":True}, ...]
            "party_count": 0,
            "input_backend": "-",
            "scanner_fps": 0.0,
            "modules": {},            # {"pot": {"state":"stopped","detail":""}, ...}
        }

    def set(self, key, value):
        with self._lock:
            self._data[key] = value

    def update(self, **kwargs):
        with self._lock:
            self._data.update(kwargs)

    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)

    def snapshot(self) -> dict:
        with self._lock:
            data = dict(self._data)
            data["party"] = list(data.get("party") or [])
            data["modules"] = dict(data.get("modules") or {})
            return data

    def set_module_state(self, name, state, detail=""):
        with self._lock:
            modules = dict(self._data.get("modules") or {})
            modules[name] = {"state": state, "detail": detail}
            self._data["modules"] = modules
