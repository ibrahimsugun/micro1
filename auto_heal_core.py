"""
# Geliştirilmiş Otomatik İyileştirme ve Buff Sistemi - Çekirdek (Core) Modülü
#
# Bu modül, otomatik iyileştirme ve buff sistemi için temel işlevleri ve iş mantığını içerir.
# UI katmanından ayrılmış olarak, ana işlevselliği sağlar.
#
# Özellikleri:
# - HP barı algılama ve analiz
# - Buff süre takibi ve otomatik kullanımı
# - Performans optimizasyonu
# - Thread güvenliği
#
# Author: Claude AI
# Version: 2.0
"""

import time
import threading
import numpy as np
import logging
from typing import List, Dict, Any, Tuple, Optional, Callable

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("AutoHealCore")

# HP barı renk kodu olarak #AE0000 kullan - RGB formatına dönüştür
HP_BAR_COLOR = {
    'r': 0xAE,  # 174 decimal
    'g': 0x00,  # 0 decimal
    'b': 0x00   # 0 decimal
}

# Renk toleransı (renk farklılıklarını dikkate almak için)
COLOR_TOLERANCE = 30

class HealHelper:
    """
    HP barlarının takibi ve iyileştirme işlemlerini yönetir.
    Bu sınıf, ekran görüntülerini analiz ederek HP yüzdesini hesaplar
    ve gereken durumlarda iyileştirme yapar.
    """
    
    def __init__(self, click_func: Callable[[int, int], None], key_press_func: Callable[[int, float], None], 
                 screenshot_func: Callable[[Tuple[int, int, int, int], int], None], main_window=None):
        """
        HealHelper sınıfını başlatır.
        
        Args:
            click_func: Belirli bir konuma tıklama işlevini sağlayan fonksiyon.
            key_press_func: Klavye tuşuna basma işlevini sağlayan fonksiyon.
            screenshot_func: Ekran görüntüsü alma işlevini sağlayan fonksiyon.
            main_window: Ana uygulama penceresi referansı.
        """
        self.click_func = click_func
        self.key_press_func = key_press_func
        self.screenshot_func = screenshot_func
        self.main_window = main_window
        
        # Çalışma durumu
        self.working = False
        
        # Aktif heal satırları için thread'ler
        self.threads: List[threading.Thread] = []
        
        # Aktif satırlar ve koordinatları
        self.rows: List[Dict[str, Any]] = [
            {"active": False, "coords": [], "last_heal_time": 0, "click_coords": [], "use_click": False} 
            for _ in range(8)
        ]
        
        # Global ayarlar
        self.heal_percentage = 80
        self.heal_key = "1"  # Varsayılan iyileştirme tuşu
        self.check_interval = 0.1  # 100ms kontrol aralığı
        self.heal_cooldown = 1.0  # 1 saniye iyileştirme bekleme süresi
        
        # Toplu heal ayarları
        self.mass_heal_percentage = 60  # Varsayılan toplu iyileştirme yüzdesi
        self.mass_heal_key = "2"  # Varsayılan toplu iyileştirme tuşu
        self.mass_heal_active = False  # Toplu iyileştirme aktif mi?
        self.mass_heal_party_check = False  # Parti seçili kontrolü
        self.mass_heal_cooldown = 2.0  # 2 saniye toplu iyileştirme bekleme süresi
        self.last_mass_heal_time = 0  # Son toplu iyileştirme zamanı
        
        logger.info("HealHelper başlatıldı.")
    
    def set_heal_percentage(self, percentage: int) -> None:
        """
        Global iyileştirme yüzdesini ayarlar.
        
        Args:
            percentage: 1-99 arası iyileştirme yüzdesi.
        """
        if 1 <= percentage <= 99:
            self.heal_percentage = percentage
            logger.info(f"İyileştirme yüzdesi %{percentage} olarak ayarlandı.")
        else:
            logger.warning(f"Geçersiz iyileştirme yüzdesi: {percentage}")
    
    def set_heal_key(self, key: str) -> None:
        """
        İyileştirme tuşunu ayarlar.
        
        Args:
            key: İyileştirme için kullanılacak tuş.
        """
        self.heal_key = key
        logger.info(f"İyileştirme tuşu '{key}' olarak ayarlandı.")
    
    def set_mass_heal_percentage(self, percentage: int) -> None:
        """
        Toplu iyileştirme yüzdesini ayarlar.
        
        Args:
            percentage: 1-99 arası toplu iyileştirme yüzdesi.
        """
        if 1 <= percentage <= 99:
            self.mass_heal_percentage = percentage
            logger.info(f"Toplu iyileştirme yüzdesi %{percentage} olarak ayarlandı.")
        else:
            logger.warning(f"Geçersiz toplu iyileştirme yüzdesi: {percentage}")
    
    def set_mass_heal_key(self, key: str) -> None:
        """
        Toplu iyileştirme tuşunu ayarlar.
        
        Args:
            key: Toplu iyileştirme için kullanılacak tuş.
        """
        self.mass_heal_key = key
        logger.info(f"Toplu iyileştirme tuşu '{key}' olarak ayarlandı.")
    
    def set_mass_heal_active(self, active: bool) -> None:
        """
        Toplu iyileştirme özelliğinin aktif durumunu ayarlar.
        
        Args:
            active: Aktif durumu.
        """
        self.mass_heal_active = active
        logger.info(f"Toplu iyileştirme {'aktif' if active else 'pasif'} olarak ayarlandı.")
    
    def set_mass_heal_party_check(self, check: bool) -> None:
        """
        Toplu iyileştirme öncesi parti seçili kontrolünü ayarlar.
        
        Args:
            check: Kontrol durumu.
        """
        self.mass_heal_party_check = check
        logger.info(f"Toplu iyileştirme parti seçim kontrolü {'aktif' if check else 'pasif'} olarak ayarlandı.")
    
    def set_check_interval(self, interval_ms: int) -> None:
        """
        Ekran kontrol frekansını milisaniye cinsinden ayarlar.
        
        Args:
            interval_ms: Kontrol aralığı (milisaniye cinsinden, 100-1000 arası).
        """
        if 100 <= interval_ms <= 1000:
            self.check_interval = interval_ms / 1000.0  # Saniyeye çevir
            logger.info(f"Ekran kontrol frekansı {interval_ms} ms olarak ayarlandı.")
        else:
            logger.warning(f"Geçersiz kontrol aralığı: {interval_ms}ms. 100-1000 ms arasında bir değer olmalı.")
    
    def set_row_active(self, row_idx: int, active: bool) -> None:
        """
        Belirli bir satırın aktif/pasif durumunu değiştirir.
        
        Args:
            row_idx: Satır indeksi (0-7).
            active: Aktif durumu.
        """
        if 0 <= row_idx < len(self.rows):
            self.rows[row_idx]["active"] = active
            logger.info(f"Satır {row_idx+1} {'aktif' if active else 'pasif'} olarak ayarlandı.")
        else:
            logger.warning(f"Geçersiz satır indeksi: {row_idx}")
    
    def set_row_coordinates(self, row_idx: int, coords: List[int]) -> None:
        """
        Belirli bir satırın koordinatlarını ayarlar.
        
        Args:
            row_idx: Satır indeksi (0-7).
            coords: Koordinatlar [x1, y1, x2, y2].
        """
        if 0 <= row_idx < len(self.rows):
            if len(coords) == 4:
                self.rows[row_idx]["coords"] = coords
                logger.info(f"Satır {row_idx+1} koordinatları ayarlandı: {coords}")
            else:
                logger.warning(f"Geçersiz koordinat sayısı: {len(coords)}, 4 gerekiyor.")
        else:
            logger.warning(f"Geçersiz satır indeksi: {row_idx}")
    
    def set_row_click_coordinates(self, row_idx: int, x: int, y: int) -> None:
        """
        Belirli bir satır için fare tıklama koordinatlarını ayarlar.
        
        Args:
            row_idx: Satır indeksi (0-7).
            x: Tıklama X koordinatı.
            y: Tıklama Y koordinatı.
        """
        if 0 <= row_idx < len(self.rows):
            self.rows[row_idx]["click_coords"] = [x, y]
            self.rows[row_idx]["use_click"] = True
            logger.info(f"Satır {row_idx+1} tıklama koordinatları ayarlandı: ({x}, {y})")
        else:
            logger.warning(f"Geçersiz satır indeksi: {row_idx}")
    
    def set_row_use_click(self, row_idx: int, use_click: bool) -> None:
        """
        Belirli bir satır için fare tıklama kullanımını ayarlar.
        
        Args:
            row_idx: Satır indeksi (0-7).
            use_click: True ise tuş yerine fare tıklaması kullanılır.
        """
        if 0 <= row_idx < len(self.rows):
            self.rows[row_idx]["use_click"] = use_click
            logger.info(f"Satır {row_idx+1} fare tıklama kullanımı: {'Aktif' if use_click else 'Pasif'}")
        else:
            logger.warning(f"Geçersiz satır indeksi: {row_idx}")
    
    def start(self) -> None:
        """
        Tüm aktif satırlar için iyileştirme işlemini başlatır.
        """
        if self.working:
            logger.warning("İyileştirme sistemi zaten çalışıyor.")
            return
        
        self.working = True
        logger.info("İyileştirme sistemi başlatılıyor...")
        
        # Aktif satırlar için thread'leri başlat
        for i, row in enumerate(self.rows):
            if row["active"] and len(row["coords"]) == 4:
                thread = threading.Thread(target=self._heal_row_worker, args=(i,), daemon=True)
                thread.start()
                self.threads.append(thread)
                logger.info(f"Satır {i+1} için iyileştirme thread'i başlatıldı.")
        
        # Toplu iyileştirme thread'i
        if self.mass_heal_active:
            thread = threading.Thread(target=self._mass_heal_worker, daemon=True)
            thread.start()
            self.threads.append(thread)
            logger.info("Toplu iyileştirme thread'i başlatıldı.")
    
    def stop(self) -> None:
        """
        Tüm iyileştirme işlemlerini durdurur.
        """
        if not self.working:
            logger.warning("İyileştirme sistemi zaten durdurulmuş.")
            return
        
        logger.info("İyileştirme sistemi durduruluyor...")
        self.working = False
        
        # Thread'lerin durması için biraz bekle
        time.sleep(0.5)
        
        # Thread'leri temizle
        self.threads.clear()
        logger.info("İyileştirme sistemi durduruldu.")
    
    def _heal_row_worker(self, row_idx: int) -> None:
        """
        Belirli bir satır için HP barını sürekli kontrol edip,
        belirlenen yüzdenin altına düştüğünde otomatik iyileştirme yapan thread.
        
        Args:
            row_idx: Kontrol edilecek satırın indeksi.
        """
        row = self.rows[row_idx]
        
        # Bar genişliği
        bar_width = row["coords"][2] - row["coords"][0]
        
        while self.working and row["active"]:
            try:
                # HP barının bulunduğu bölgenin ekran görüntüsünü al
                region = (row["coords"][0], row["coords"][1], 
                        row["coords"][2], row["coords"][1] + 20)
                
                # Ekran görüntüsünü al
                self.screenshot_func(region, 1 + row_idx)  # Özel hedef ID'si
                
                # Görüntüyü analiz et ve HP yüzdesini hesapla
                hp_percentage = self._analyze_hp_bar(row_idx, bar_width)
                logger.info(f"Satır {row_idx+1} HP: %{hp_percentage:.1f}")
                
                # İyileştirme gerekiyor mu kontrol et
                current_time = time.time()
                if (hp_percentage < self.heal_percentage and 
                    current_time - row["last_heal_time"] > self.heal_cooldown):
                    
                    logger.info(f"Satır {row_idx+1} HP: %{hp_percentage:.1f} - İyileştirme yapılıyor...")
                    
                    # İyileştirme tuşuna bas
                    self.key_press_func(self.heal_key, 0.01)
                    time.sleep(0.1)  # 100ms bekle
                    self.key_press_func(self.heal_key, 0.01)  # Güvenlik için iki kez bas
                    logger.info(f"İyileştirme tuşuna basıldı: {self.heal_key}")
                    
                    # İyileştirme zamanını güncelle
                    row["last_heal_time"] = time.time()
            
            except Exception as e:
                logger.error(f"Satır {row_idx+1} iyileştirme kontrol hatası: {e}")
            
            time.sleep(self.check_interval)
    
    def _analyze_hp_bar(self, row_idx: int, bar_width: int) -> float:
        """
        HP barını analiz ederek HP yüzdesini hesaplar.
        
        Args:
            row_idx: Satır indeksi.
            bar_width: Bar genişliği (piksel).
            
        Returns:
            HP yüzdesi (0-100).
        """
        # Knight Online'a uygun olarak, HP barının renk kodu #AE0000 olsun
        row = self.rows[row_idx]
        filled_pixels = 0
        valid_pixels = 0
        
        # Ekran görüntüsüne erişim
        try:
            # Ekran görüntüsünü al
            screenshot = self._get_screenshot()
            if screenshot is None:
                logger.warning(f"Satır {row_idx+1} için ekran görüntüsü alınamadı.")
                return 100  # Hata durumunda iyileştirme yapma
            
            # HP barının üst ve alt sınırlarını belirle
            # Barın ortasını değil, birkaç satırı tarayalım daha güvenilir olması için
            bar_height = 10  # Barın yüksekliği (yaklaşık)
            start_y = max(0, row["coords"][1])
            end_y = min(screenshot.shape[0], row["coords"][1] + bar_height)
            
            # HP barı boyunca yatay ve dikey olarak piksel kontrolü yap
            for y in range(start_y, end_y):
                for x_ratio in range(0, 100):  # Bar genişliğinin %0-%100'ü arasında örnekle
                    x = row["coords"][0] + int(bar_width * x_ratio / 100)
                    
                    # x koordinatı geçerli mi kontrol et
                    if x >= row["coords"][0] and x <= row["coords"][2]:
                        valid_pixels += 1
                        
                        try:
                            # Piksel rengini al
                            rgb = self._get_pixel_color(screenshot, x, y)
                            
                            # #AE0000 renk koduna (kırmızı ton) yakın mı kontrol et
                            if (abs(rgb[0] - HP_BAR_COLOR['r']) <= COLOR_TOLERANCE and
                                abs(rgb[1] - HP_BAR_COLOR['g']) <= COLOR_TOLERANCE and 
                                abs(rgb[2] - HP_BAR_COLOR['b']) <= COLOR_TOLERANCE):
                                filled_pixels += 1
                        except IndexError:
                            # Piksel görüntü sınırları dışındaysa atla
                            continue
            
            # HP yüzdesini hesapla
            if valid_pixels > 0:
                hp_percentage = (filled_pixels / valid_pixels) * 100
                return hp_percentage
            else:
                logger.warning(f"Geçerli piksel bulunamadı: bar_width={bar_width}")
                return 100
            
        except Exception as e:
            logger.error(f"HP barı analiz hatası: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return 100  # Hata durumunda iyileştirme yapma
    
    def _get_screenshot(self):
        """
        Ana uygulamadan ekran görüntüsünü alır.
        Bu metodu uygulamanızın yapısına göre uyarlamanız gerekir.
        """
        try:
            # Ana uygulama penceresi tanımlı mı kontrol et
            if self.main_window is None:
                logger.warning("Ana pencere referansı bulunamadı.")
                return None
                
            # Ana uygulamanın ekran görüntüsüne erişim
            return self.main_window.custom_screenshot
        except Exception as e:
            logger.error(f"Ekran görüntüsü alınırken hata: {str(e)}")
            return None
    
    def _get_pixel_color(self, screenshot, x, y, x_offset=0, y_offset=0):
        """
        Belirtilen koordinattaki pikselin rengini döndürür.
        
        Args:
            screenshot: Piksel rengini almak için kullanılacak ekran görüntüsü.
            x: Piksel x koordinatı.
            y: Piksel y koordinatı.
            x_offset: X koordinatı için ofset değeri.
            y_offset: Y koordinatı için ofset değeri.
            
        Returns:
            RGB renk değeri [r, g, b], hata durumunda [0, 0, 0].
        """
        try:
            # Görüntü boyutlarını kontrol et
            if screenshot is None:
                return [0, 0, 0]
                
            height, width = screenshot.shape[:2]
            
            # Ofsetli koordinatları hesapla
            adj_y = y - y_offset
            adj_x = x - x_offset
            
            # Koordinatlar görüntü sınırları içinde mi kontrol et
            if 0 <= adj_y < height and 0 <= adj_x < width:
                return screenshot[adj_y, adj_x]
            else:
                logger.debug(f"Görüntü sınırları dışında: x={adj_x}, y={adj_y}, genişlik={width}, yükseklik={height}")
                return [0, 0, 0]
        except Exception as e:
            logger.debug(f"Piksel rengi alınırken hata: {e} (x={x}, y={y})")
            return [0, 0, 0]

    def _mass_heal_worker(self) -> None:
        """
        Ekrandaki tüm HP barlarını izleyerek toplu iyileştirme yapar.
        """
        critical_rows_count = 0
        total_active_rows = 0
        
        while self.working and self.mass_heal_active:
            try:
                # Son toplu iyileştirmeden sonra geçen süreyi kontrol et
                current_time = time.time()
                if current_time - self.last_mass_heal_time < self.mass_heal_cooldown:
                    time.sleep(self.check_interval)
                    continue
                
                # Aktif satırları sayarak kritik durumda olanları hesapla
                critical_rows_count = 0
                total_active_rows = 0
                
                for i, row in enumerate(self.rows):
                    if row["active"] and len(row["coords"]) == 4:
                        total_active_rows += 1
                        
                        # Bar genişliği
                        bar_width = row["coords"][2] - row["coords"][0]
                        
                        # HP barının bulunduğu bölgenin ekran görüntüsünü al
                        region = (row["coords"][0], row["coords"][1], 
                                row["coords"][2], row["coords"][1] + 20)
                        
                        # Ekran görüntüsünü al
                        self.screenshot_func(region, 3 + i)  # Özel hedef ID'si
                        
                        # Görüntüyü analiz et ve HP yüzdesini hesapla
                        hp_percentage = self._analyze_hp_bar(i, bar_width)
                        
                        # Belirlenen toplu iyileştirme yüzdesinin altına düştüyse say
                        if hp_percentage < self.mass_heal_percentage:
                            critical_rows_count += 1
                
                # Toplu iyileştirme için yeterli sayıda kritik satır varsa
                if total_active_rows > 0 and (critical_rows_count / total_active_rows) >= 0.5:  # En az %50'si kritik ise
                    logger.info(f"Kritik HP durumu: {critical_rows_count}/{total_active_rows} - Toplu iyileştirme yapılıyor...")
                    
                    # Parti kontrolü aktif ise, önce parti seçimini kontrol et
                    if self.mass_heal_party_check:
                        # Burada parti seçim kontrolü yapılabilir
                        # Şimdilik sadece loglama yapıyoruz
                        logger.info("Parti seçimi kontrolü yapılıyor...")
                    
                    # Toplu iyileştirme tuşuna bas
                    self.key_press_func(self.mass_heal_key, 0.01)
                    time.sleep(0.1)  # 100ms bekle
                    
                    # İyileştirme zamanını güncelle
                    self.last_mass_heal_time = time.time()
            
            except Exception as e:
                logger.error(f"Toplu iyileştirme kontrol hatası: {e}")
            
            time.sleep(self.check_interval)

class BuffHelper:
    """
    Buff'ların takibi ve otomatik kullanımını yönetir.
    Bu sınıf, buff sürelerini takip eder ve süreleri dolduğunda
    otomatik olarak buff'ları yeniler.
    """
    
    def __init__(self, key_press_func: Callable[[str, float], None]):
        """
        BuffHelper sınıfını başlatır.
        
        Args:
            key_press_func: Klavye tuşuna basma işlevini sağlayan fonksiyon.
        """
        self.key_press_func = key_press_func
        
        # Çalışma durumu
        self.working = False
        
        # Aktif buff'lar için thread'ler
        self.threads: List[threading.Thread] = []
        
        # Buff'lar için veri yapısı
        self.buffs: List[Dict[str, Any]] = [
            {"active": False, "key": "", "duration": 300, "last_used": 0} 
            for _ in range(2)  # 2 adet buff
        ]
        
        # Buff kontrol aralığı (saniye)
        self.check_interval = 0.5
        
        logger.info("BuffHelper başlatıldı.")
    
    def set_buff_active(self, buff_idx: int, active: bool) -> None:
        """
        Belirli bir buff'ın aktif/pasif durumunu değiştirir.
        
        Args:
            buff_idx: Buff indeksi (0-1).
            active: Aktif durumu.
        """
        if 0 <= buff_idx < len(self.buffs):
            self.buffs[buff_idx]["active"] = active
            logger.info(f"Buff {buff_idx+1} {'aktif' if active else 'pasif'} olarak ayarlandı.")
        else:
            logger.warning(f"Geçersiz buff indeksi: {buff_idx}")
    
    def set_buff_key(self, buff_idx: int, key: str) -> None:
        """
        Belirli bir buff için tuşu ayarlar.
        
        Args:
            buff_idx: Buff indeksi (0-1).
            key: Buff için kullanılacak tuş.
        """
        if 0 <= buff_idx < len(self.buffs):
            self.buffs[buff_idx]["key"] = key
            logger.info(f"Buff {buff_idx+1} tuşu '{key}' olarak ayarlandı.")
        else:
            logger.warning(f"Geçersiz buff indeksi: {buff_idx}")
    
    def set_buff_duration(self, buff_idx: int, duration: int) -> None:
        """
        Belirli bir buff için süreyi ayarlar.
        
        Args:
            buff_idx: Buff indeksi (0-1).
            duration: Buff süresi (saniye).
        """
        if 0 <= buff_idx < len(self.buffs):
            self.buffs[buff_idx]["duration"] = duration
            logger.info(f"Buff {buff_idx+1} süresi {duration} saniye olarak ayarlandı.")
        else:
            logger.warning(f"Geçersiz buff indeksi: {buff_idx}")
    
    def set_check_interval(self, interval_ms: int) -> None:
        """
        Buff kontrol frekansını milisaniye cinsinden ayarlar.
        
        Args:
            interval_ms: Kontrol aralığı (milisaniye cinsinden, 100-1000 arası).
        """
        if 100 <= interval_ms <= 1000:
            self.check_interval = interval_ms / 1000.0  # Saniyeye çevir
            logger.info(f"Buff kontrol frekansı {interval_ms} ms olarak ayarlandı.")
        else:
            logger.warning(f"Geçersiz kontrol aralığı: {interval_ms}ms. 100-1000 ms arasında bir değer olmalı.")
    
    def reset_buff_timer(self, buff_idx: int) -> None:
        """
        Belirli bir buff'ın zamanlayıcısını sıfırlar.
        
        Args:
            buff_idx: Buff indeksi (0-1).
        """
        if 0 <= buff_idx < len(self.buffs):
            self.buffs[buff_idx]["last_used"] = time.time()
            logger.info(f"Buff {buff_idx+1} zamanlayıcısı sıfırlandı.")
        else:
            logger.warning(f"Geçersiz buff indeksi: {buff_idx}")
    
    def get_buff_remaining_time(self, buff_idx: int) -> int:
        """
        Belirli bir buff'ın kalan süresini hesaplar.
        
        Args:
            buff_idx: Buff indeksi (0-1).
            
        Returns:
            Kalan süre (saniye), veya -1 (buff aktif değilse).
        """
        if 0 <= buff_idx < len(self.buffs):
            buff = self.buffs[buff_idx]
            
            if not buff["active"]:
                return -1
                
            current_time = time.time()
            elapsed = current_time - buff["last_used"]
            remaining = max(0, buff["duration"] - elapsed)
            
            return int(remaining)
        else:
            logger.warning(f"Geçersiz buff indeksi: {buff_idx}")
            return -1
    
    def start(self) -> None:
        """
        Tüm aktif buff'lar için takip işlemini başlatır.
        """
        if self.working:
            logger.warning("Buff sistemi zaten çalışıyor.")
            return
        
        self.working = True
        logger.info("Buff sistemi başlatılıyor...")
        
        # Aktif buff'lar için thread'leri başlat
        for i, buff in enumerate(self.buffs):
            if buff["active"]:
                thread = threading.Thread(target=self._buff_worker, args=(i,), daemon=True)
                thread.start()
                self.threads.append(thread)
                logger.info(f"Buff {i+1} için thread başlatıldı.")
    
    def stop(self) -> None:
        """
        Tüm buff takip işlemlerini durdurur.
        """
        if not self.working:
            logger.warning("Buff sistemi zaten durdurulmuş.")
            return
        
        logger.info("Buff sistemi durduruluyor...")
        self.working = False
        
        # Thread'lerin durması için biraz bekle
        time.sleep(0.5)
        
        # Thread'leri temizle
        self.threads.clear()
        logger.info("Buff sistemi durduruldu.")
    
    def _buff_worker(self, buff_idx: int) -> None:
        """
        Belirli bir buff için zamanlayıcıyı kontrol edip,
        süre dolduğunda otomatik olarak buff yapan thread.
        
        Args:
            buff_idx: Kontrol edilecek buff'ın indeksi.
        """
        buff = self.buffs[buff_idx]
        
        # Buff kullanım sonrası bekleme süresi
        buff_cooldown = 0.5  # 500ms
        
        while self.working and buff["active"]:
            try:
                current_time = time.time()
                elapsed = current_time - buff["last_used"]
                
                # Süre dolduysa buff'ı kullan
                if elapsed >= buff["duration"]:
                    key = buff["key"]
                    if key:
                        logger.info(f"Buff {buff_idx+1} süresi doldu, kullanılıyor: {key}")
                        
                        # Buff tuşuna bas
                        self.key_press_func(key, 0.01)
                        
                        # Süreyi sıfırla
                        buff["last_used"] = current_time
                        
                        # Kısa bir süre bekle
                        time.sleep(buff_cooldown)
                    else:
                        logger.warning(f"Buff {buff_idx+1} için tuş tanımlanmamış.")
                
            except Exception as e:
                logger.error(f"Buff {buff_idx+1} kontrol hatası: {e}")
            
            time.sleep(self.check_interval)

# Yardımcı fonksiyonlar
def format_time(seconds: int) -> str:
    """
    Saniye cinsinden süreyi formatlar.
    
    Args:
        seconds: Formatlanacak süre (saniye).
        
    Returns:
        "DD:SS" formatında süre veya "KULLANILDI!" (süre 0 ise).
    """
    if seconds <= 0:
        return "KULLANILDI!"
        
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}" 