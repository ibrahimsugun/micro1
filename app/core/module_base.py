"""Modül taban sınıfı: kendi thread'i, kendi döngü hızı, kendi hata sayacı.

Kural: worker -> UI yalnız pyqtSignal ile konuşur. Modüller birbirinden
bağımsızdır; biri hata verip durduğunda diğerleri etkilenmez.
"""

import threading
import time

from PyQt5.QtCore import QObject, pyqtSignal

from . import vision
from ..constants import (
    BEEP_ERROR,
    CALIB_RPR,
    MAX_MODULE_ERRORS,
    RPR_BURNT_COLOR_BGR,
    RPR_TRIGGER_FRACTION,
    THREAD_JOIN_TIMEOUT,
)

STATE_STOPPED = "stopped"
STATE_WAITING = "waiting"
STATE_RUNNING = "running"
STATE_ERROR = "error"

STATE_LABELS = {
    STATE_STOPPED: "Durdu",
    STATE_WAITING: "Bekliyor",
    STATE_RUNNING: "Çalışıyor",
    STATE_ERROR: "HATA",
}


class ModuleContext:
    """Modüllere geçirilen ortak servis demeti."""

    def __init__(self, app_state, input_service, scanner, calibration, live_status, sound):
        self.state = app_state
        self.input = input_service
        self.scanner = scanner
        self.calibration = calibration
        self.live = live_status
        self.sound = sound
        # Kare damgalı okuma hafızası: aynı kare içinde ikinci kez sorulan
        # değer yeniden hesaplanmaz. Modüller kendi hızlarında döndüğü için
        # (attack 20 Hz, tarayıcı 10 Hz) okumaların yarısı birebir aynı sonucu
        # üretiyordu. Kilit yalnız sözlük işlemi kadar tutulur.
        self._memo = {}
        self._memo_stamp = None
        self._memo_lock = threading.Lock()

    # ------------------------------------------------------------------ kare
    def frame_stamp(self):
        """Tarayıcının o anki kare damgası."""
        return self.scanner.stamp()

    def wait_new_frame(self, since_stamp, timeout=1.0) -> bool:
        """Yeni kare gelene kadar bekler (frame_driven modüller için)."""
        return self.scanner.wait_for_frame(since_stamp, timeout)

    def _cached(self, key, compute):
        """Aynı kare içinde tekrarlanan okumayı yeniden hesaplamaz."""
        stamp = self.scanner.stamp()
        with self._memo_lock:
            if stamp != self._memo_stamp:
                self._memo.clear()
                self._memo_stamp = stamp
            elif key in self._memo:
                return self._memo[key]
        value = compute()
        with self._memo_lock:
            if stamp == self._memo_stamp:
                self._memo[key] = value
        return value

    # -- ortak ekran okuma yardımcıları (modüller kendi thread'lerinden çağırır) --
    def bar_percent(self, name):
        """Kalibre bölgenin doluluk yüzdesi; kayıt/kare yoksa None.

        Bölgede BAR GEOMETRİSİ kayıtlıysa ölçüm tümdengelimle yapılır: barın
        boş kısmı sayılır, dolu kısmın rengi (mor/turuncu/yeşil debuff) sonucu
        değiştirmez. Geometri yoksa eski tümevarım yolu kullanılır — mp_bar,
        target_bar ve geometrisi henüz çıkarılmamış eski profiller.
        """
        region = self.calibration.get(name)
        if not region.saved or not region.rect:
            return None
        return self._cached(
            ("percent", name, region.rect), lambda: self._measure_percent(region)
        )

    def _measure_percent(self, region):
        img = self.scanner.region(region.rect)
        if img is None:
            return None
        if region.bar_geom is not None:
            return vision.bar_percent_by_empty(img, region.bar_geom)
        return vision.bar_percent(img, region.ref_color, ratio_full=region.ratio_full)

    def bar_state(self, name):
        """Barın renk durumu anahtarı (yalnız BİLGİ amaçlı); yoksa None.

        Hiçbir modül kararına bağlı değildir; StatusReader arayüzde göstermek
        için çağırır.
        """
        region = self.calibration.get(name)
        if not region.saved or not region.rect or region.bar_geom is None:
            return None
        return self._cached(
            ("state", name, region.rect),
            lambda: vision.bar_state(self.scanner.region(region.rect), region.bar_geom),
        )

    def region_image(self, name):
        region = self.calibration.get(name)
        if not region.saved or not region.rect:
            return None
        return self.scanner.region(region.rect)

    def rpr_ratio(self):
        """Silah alanındaki YANIK renk oranı (0.0-1.0); kayıt yoksa None.

        Renk tabanlıdır: kılıcın yönü, hangi elde olduğu ve animasyon fark
        etmez. Referans SABİT yanık kırmızısıdır (RPR_BURNT_COLOR_BGR); kayıt
        anındaki değişken/dalgalı renge bağlı değildir. Eski (şablonlu)
        kayıtlarda None döner, şablon yoluna düşülür.
        """
        region = self.calibration.get(CALIB_RPR)
        if not region.saved or not region.rect or not region.ref_color:
            return None
        return self._cached(
            ("rpr", region.rect), lambda: self._measure_rpr(region)
        )

    def _measure_rpr(self, region):
        img = self.scanner.region(region.rect)
        if img is None:
            return None
        # Kayıtlı ref_color DEĞİL, sabit yanık kırmızısı: yalnız tam yanık
        # (doygun kırmızı) yakalanır, arka plandan ve kayıt hatasından bağımsız.
        return vision.color_presence_ratio(img, RPR_BURNT_COLOR_BGR)

    def rpr_broken(self) -> bool:
        """Silah(lar)dan en az biri yanık mı?"""
        region = self.calibration.get(CALIB_RPR)
        if not region.saved or not region.rect:
            return False
        ratio = self.rpr_ratio()
        if ratio is not None:
            trigger = max(0.002, region.ratio_full * RPR_TRIGGER_FRACTION)
            return ratio >= trigger
        # Geriye dönük: renk yerine şablon kaydedilmiş eski profiller.
        template = region.template()
        if template is None:
            return False
        matched, _score = vision.template_match(
            self.scanner.region(region.rect), template
        )
        return matched


class ModuleBase(QObject):
    statusChanged = pyqtSignal(str, str, str)   # (modül kimliği, durum, açıklama)
    selfDisabled = pyqtSignal(str, str)         # (modül kimliği, sebep)

    module_id = "base"
    required_calibrations = ()
    # True: tick tamamen ekran okumasıyla çalışıyor -> yeni kare gelmeden
    # tekrar dönmez. loop_ms bu durumda ALT SINIR olur; efektif hız
    # min(kullanıcının seçtiği hız, tarayıcı kare hızı) olur. Sayaçla çalışan
    # modüller (attack, clicker) False kalır, zamanlamaları bozulmasın.
    frame_driven = False

    def __init__(self, ctx: ModuleContext, loop_ms: int, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.loop_ms = int(loop_ms)
        self._enabled = False
        self._stop = threading.Event()
        self._thread = None
        self._error_count = 0
        self._state = STATE_STOPPED
        self._detail = ""
        self._was_active = False
        self._cfg_lock = threading.Lock()

    # ------------------------------------------------------------------ ayarlar
    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, value: bool):
        value = bool(value)
        if value == self._enabled:
            return
        self._enabled = value
        if value:
            self._error_count = 0
        self._publish(STATE_WAITING if value else STATE_STOPPED, "")

    def set_loop_ms(self, value: int):
        self.loop_ms = max(5, int(value))

    # ------------------------------------------------------------------ yaşam
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name=f"Module-{self.module_id}", daemon=True
        )
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=THREAD_JOIN_TIMEOUT)
            self._thread = None

    # ------------------------------------------------------------------ durum
    @property
    def state(self) -> str:
        return self._state

    def _publish(self, state, detail=""):
        if state == self._state and detail == self._detail:
            return
        self._state = state
        self._detail = detail
        if self.ctx.live is not None:
            self.ctx.live.set_module_state(self.module_id, state, detail)
        self.statusChanged.emit(self.module_id, state, detail)

    # ------------------------------------------------------------------ döngü
    def _run(self):
        while not self._stop.is_set():
            started = time.monotonic()
            if self._state == STATE_ERROR:
                self._stop.wait(0.2)
                continue
            if not self._enabled:
                if self._was_active:
                    self._was_active = False
                    self._safe_deactivate()
                self._publish(STATE_STOPPED, "")
                self._stop.wait(0.1)
                continue
            if not self.ctx.state.modules_may_run():
                if self._was_active:
                    self._was_active = False
                    self._safe_deactivate()
                self._publish(STATE_WAITING, self.ctx.state.reason_blocked())
                self._stop.wait(0.1)
                continue

            if not self._was_active:
                self._was_active = True
                self._safe_activate()
            self._publish(STATE_RUNNING, "")

            stamp = self.ctx.frame_stamp() if self.frame_driven else None
            try:
                self.tick()
                self._error_count = 0
            except Exception as exc:
                self._error_count += 1
                if self._error_count >= MAX_MODULE_ERRORS:
                    self._enabled = False
                    self._was_active = False
                    self._publish(STATE_ERROR, str(exc)[:120])
                    if self.ctx.sound is not None:
                        self.ctx.sound.beep(BEEP_ERROR)
                    self.selfDisabled.emit(self.module_id, str(exc)[:200])
                    continue
                self._stop.wait(0.1)

            remaining = (self.loop_ms / 1000.0) - (time.monotonic() - started)
            if remaining > 0:
                self._stop.wait(remaining)
            if self.frame_driven and stamp is not None and not self._stop.is_set():
                # Yeni kare gelmeden yeniden okumak aynı sonucu verir.
                self.ctx.wait_new_frame(stamp, max(0.25, self.loop_ms / 1000.0))

    def _safe_activate(self):
        try:
            self.on_activate()
        except Exception:
            pass

    def _safe_deactivate(self):
        try:
            self.on_deactivate()
        except Exception:
            pass

    def clear_error(self):
        """Kullanıcı modülü yeniden açtığında hata kilidini kaldırır."""
        self._error_count = 0
        if self._state == STATE_ERROR:
            self._publish(STATE_STOPPED, "")

    # ------------------------------------------------------------------ arayüz
    def tick(self):
        raise NotImplementedError

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass


class Cooldown:
    """Monotonic damgalı basit bekleme sayacı."""

    def __init__(self, interval_ms=0):
        self.interval = interval_ms / 1000.0
        self._last = 0.0

    def set_interval_ms(self, interval_ms):
        self.interval = max(0.0, interval_ms / 1000.0)

    def ready(self, now=None) -> bool:
        now = time.monotonic() if now is None else now
        return (now - self._last) >= self.interval

    def stamp(self, now=None):
        self._last = time.monotonic() if now is None else now

    def reset(self):
        self._last = 0.0

    def remaining(self, now=None) -> float:
        now = time.monotonic() if now is None else now
        return max(0.0, self.interval - (now - self._last))
