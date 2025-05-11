"""
# Knight Online Geliştirilmiş Otomatik İyileştirme ve Buff Sistemi - Ana Giriş Programı
#
# Bu dosya, otomatik iyileştirme ve buff sisteminin ana giriş noktasıdır.
# Programı başlatmak için bu dosyayı çalıştırın.
#
# Modüler yapı:
# - auto_heal_core.py: Temel iyileştirme ve buff mantığını içerir
# - auto_heal_ui.py: Kullanıcı arayüzü bileşenlerini içerir
# - auto_heal_buff.py: İçe aktarma yardımcı modülü
#
# Özellikleri:
# - Çoklu HP barı takibi ve otomatik iyileştirme
# - Zamanlayıcılı buff sistemi
# - Kullanıcı dostu arayüz
# - Ayarları kaydetme/yükleme
#
# Author: Claude AI
# Version: 2.0
"""

import os
import sys
import time
import configparser
import threading
import logging
import pyautogui
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStatusBar
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon, QFont
from pynput.keyboard import Listener, Key

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("AutoHealMain")

# Win32api için içe aktarma
try:
    import win32api
    import win32con
    win32api_available = True
    logger.info("Win32API başarıyla içe aktarıldı.")
except ImportError:
    win32api_available = False
    logger.warning("Win32API bulunamadı, PyAutoGUI kullanılacak.")

# MSS kütüphanesini dikkatli bir şekilde içe aktar
try:
    import mss.tools
    import mss.windows
    # Windows sürümünü kontrol et ve MSS uyumluluğunu belirle
    import platform
    win_ver = platform.win32_ver()[1]
    # Windows 11 veya üzeri sürümlerde MSS ile bazı sorunlar olabilir
    # Bu durumda MSS yerine PyAutoGUI kullanmayı tercih edebiliriz
    if int(win_ver.split('.')[0]) >= 10 and int(win_ver.split('.')[1]) >= 22000:
        mss_recommended = False
        logger.warning(f"Windows 11 veya üzeri tespit edildi (sürüm: {win_ver}). PyAutoGUI tercih edilecek.")
    else:
        mss_recommended = True
    mss_available = True
except ImportError:
    mss_available = False
    mss_recommended = False
    logger.warning("MSS kütüphanesi yüklenemedi. PyAutoGUI kullanılacak.")
except Exception as e:
    mss_available = False
    mss_recommended = False
    logger.warning(f"MSS kütüphanesi yüklenirken hata: {e}")

# Tuş basma için interception kütüphanesini içe aktar (varsa)
try:
    from interception import *
    from stroke import *
    from consts import *
    interception_available = True
except ImportError:
    interception_available = False

# Modülleri içe aktar
from auto_heal_core import HealHelper, BuffHelper
from auto_heal_ui import AutoHealUI, AutoHealBuffWidget, HealRowWidget, BuffWidget

class ScreenService:
    """Ekran görüntüsü alma işlemlerini yöneten servis."""
    
    def __init__(self):
        self.mss_available = False
        self.sct = None
        self.current_screenshot = None
        self.use_mss = False
        
        # MSS kütüphanesini başlatmayı dene
        if mss_available and mss_recommended:
            try:
                logger.info("MSS kütüphanesi başlatılıyor...")
                self.sct = mss.mss()
                # Test amaçlı bir ekran görüntüsü almayı dene
                test_img = self.sct.grab(self.sct.monitors[0])
                if test_img:
                    self.mss_available = True
                    self.use_mss = True
                    logger.info("MSS başarıyla başlatıldı ve test edildi.")
                else:
                    logger.warning("MSS test başarısız oldu. PyAutoGUI kullanılacak.")
            except Exception as e:
                logger.error(f"MSS başlatılırken hata: {e}")
                self.sct = None
                
        if not self.mss_available:
            logger.info("PyAutoGUI ekran görüntüsü alma servisi kullanılacak.")
        
    def take_screenshot(self, region=None, target_id=None):
        """
        Belirtilen bölgenin ekran görüntüsünü alır.
        
        Args:
            region: (x, y, width, height) formatında bölge bilgisi.
            target_id: Hedef kimliği (opsiyonel).
        """
        # PyAutoGUI ile ekran görüntüsü alma (varsayılan ve güvenli yöntem)
        try:
            # MSS kütüphanesi kullanma seçeneği etkin ve kullanılabilir değilse
            if not self.use_mss or not self.mss_available:
                if region:
                    x, y, x2, y2 = region
                    width = x2 - x
                    height = y2 - y
                    img = pyautogui.screenshot(region=(x, y, width, height))
                else:
                    img = pyautogui.screenshot()
                
                # PIL görüntüsünü NumPy dizisine dönüştür
                img_np = np.array(img)
                self.current_screenshot = img_np
                return img_np
            
            # MSS ile ekran görüntüsü alma (daha hızlı ama sorunlu olabilir)
            if region:
                x, y, x2, y2 = region
                width = x2 - x
                height = y2 - y
                
                sct_region = {"top": y, "left": x, "width": width, "height": height}
                
                try:
                    sct_img = self.sct.grab(sct_region)
                    
                    # Numpy dizisine dönüştür
                    img = np.array(sct_img)
                    self.current_screenshot = img
                    
                    # Debug için kaydet
                    if getattr(self, 'debug_mode', False):
                        debug_file = f"debug_screenshot_{target_id}_{time.time()}.png"
                        from PIL import Image
                        img_pil = Image.fromarray(img)
                        img_pil.save(os.path.join("images", debug_file))
                    
                    logger.debug(f"MSS ile ekran görüntüsü alındı: {region}")
                    return img
                    
                except Exception as mss_error:
                    logger.error(f"MSS ile ekran görüntüsü alınırken hata: {mss_error}")
                    # MSS sorunluysa PyAutoGUI'ye geç ve sonraki işlemlerde MSS'yi kullanma
                    self.use_mss = False
                    self.mss_available = False
                    
                    # PyAutoGUI ile tekrar dene
                    img = pyautogui.screenshot(region=(x, y, width, height))
                    img_np = np.array(img)
                    self.current_screenshot = img_np
                    return img_np
            else:
                # Tüm ekranın görüntüsünü al
                try:
                    if self.use_mss and self.mss_available:
                        sct_img = self.sct.grab(self.sct.monitors[0])
                        img = np.array(sct_img)
                    else:
                        img = np.array(pyautogui.screenshot())
                    
                    self.current_screenshot = img
                    logger.debug("Tüm ekranın görüntüsü alındı.")
                    return img
                except Exception as e:
                    logger.error(f"Tüm ekran görüntüsü alınırken hata: {e}")
                    # MSS sorunluysa PyAutoGUI'ye geç
                    self.use_mss = False
                    
                    # Son bir deneme daha yap
                    try:
                        img = np.array(pyautogui.screenshot())
                        self.current_screenshot = img
                        return img
                    except:
                        self.current_screenshot = None
                        return None
                    
        except Exception as e:
            logger.error(f"Ekran görüntüsü alınırken hata: {e}")
            self.current_screenshot = None
            return None


class KeyboardMouseService:
    """Klavye ve fare işlemlerini yöneten servis."""
    
    def __init__(self):
        self.keyboard = None
        self.driver = None
        self.keycodes = {"F1": 0x3B, "F2": 0x3C, "F3": 0x3D, "F4": 0x3E, "F5": 0x3F, "F6": 0x40, "F7": 0x41,
                        "F8": 0x42, "F9": 0x43, "F10": 0x44, "F11": 0x57, "F12": 0x58, "F13": 0x64, "F14": 0x65,
                        "F15": 0x66, "0": 0x0B, "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06, "6": 0x07,
                        "7": 0x08, "8": 0x09, "9": 0x0A, "A": 0x1E, "B": 0x30, "C": 0x2E, "D": 0x20, "E": 0x12,
                        "F": 0x21, "G": 0x22, "H": 0x23, "I": 0x17, "J": 0x24, "K": 0x25, "L": 0x26, "M": 0x32,
                        "N": 0x31, "O": 0x18, "P": 0x19, "Q": 0x10, "R": 0x13, "S": 0x1F, "T": 0x14, "U": 0x16,
                        "V": 0x2F, "W": 0x11, "X": 0x2D, "Y": 0x15, "Z": 0x2C}
        
        # Interception kütüphanesi kullanılabilir ise, başlat
        if interception_available:
            try:
                self.driver = interception()
                for i in range(MAX_DEVICES):
                    if interception.is_keyboard(i):
                        self.keyboard = i
                        logger.info(f"Klavye bulundu: {i}")
                        break
                if self.keyboard is None:
                    logger.warning("Klavye bulunamadı.")
            except Exception as e:
                logger.error(f"Interception sürücüsü yüklenirken hata: {e}")
                self.driver = None
                self.keyboard = None
    
    def click(self, x, y):
        """
        Belirtilen konuma tıklar.
        
        Win32API kullanılabilirse donanım düzeyinde gerçek tıklama yapar,
        yoksa PyAutoGUI kullanır.
        
        Args:
            x: X koordinatı.
            y: Y koordinatı.
        """
        try:
            if win32api_available:
                # Donanım düzeyinde gerçek tıklama yapma (Win32API)
                self.leftclick_win32(x, y)
            else:
                # PyAutoGUI ile tıklama
                pyautogui.click(x, y)
            logger.debug(f"Sol tıklama: ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"Sol tıklama işlemi başarısız: {e}")
            return False
    
    def right_click(self, x, y):
        """
        Belirtilen konuma sağ tıklar.
        
        Win32API kullanılabilirse donanım düzeyinde gerçek tıklama yapar,
        yoksa PyAutoGUI kullanır.
        
        Args:
            x: X koordinatı.
            y: Y koordinatı.
        """
        try:
            if win32api_available:
                # Donanım düzeyinde gerçek sağ tıklama yapma (Win32API)
                self.rightclick_win32(x, y)
            else:
                # PyAutoGUI ile sağ tıklama
                pyautogui.rightClick(x, y)
            logger.debug(f"Sağ tıklama: ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"Sağ tıklama işlemi başarısız: {e}")
            return False
    
    def leftclick_win32(self, x, y):
        """
        Win32API kullanarak belirtilen koordinatlarda sol fare tıklaması gerçekleştirir.
        
        Args:
            x: Tıklama x koordinatı
            y: Tıklama y koordinatı
        """
        try:
            # Fare imlecini konumlandır
            win32api.SetCursorPos((x, y))
            # Kısa bekleme
            time.sleep(0.05)
            # Sol tuşa basma olayı
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
            # Basma ve bırakma arasında bekleme
            time.sleep(0.1)
            # Sol tuşu bırakma olayı
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
            return True
        except Exception as e:
            logger.error(f"Win32API sol tıklama hatası: {e}")
            # Hata durumunda PyAutoGUI ile dene
            pyautogui.click(x, y)
            return False
    
    def rightclick_win32(self, x, y):
        """
        Win32API kullanarak belirtilen koordinatlarda sağ fare tıklaması gerçekleştirir.
        
        Args:
            x: Tıklama x koordinatı
            y: Tıklama y koordinatı
        """
        try:
            # Fare imlecini konumlandır
            win32api.SetCursorPos((x, y))
            # Kısa bekleme
            time.sleep(0.05)
            # Sağ tuşa basma olayı
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, x, y, 0, 0)
            # Basma ve bırakma arasında bekleme
            time.sleep(0.1)
            # Sağ tuşu bırakma olayı
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, x, y, 0, 0)
            return True
        except Exception as e:
            logger.error(f"Win32API sağ tıklama hatası: {e}")
            # Hata durumunda PyAutoGUI ile dene
            pyautogui.rightClick(x, y)
            return False
    
    def press_key(self, key, duration=0.01):
        """
        Belirtilen tuşa basar.
        
        Args:
            key: Basılacak tuş.
            duration: Tuşa basılı tutma süresi (saniye).
        """
        try:
            # İnterception kütüphanesi kullanılabilir ve sürücü başlatıldı ise
            if interception_available and self.driver is not None and self.keyboard is not None:
                keycode = self.keycodes.get(key.upper(), None)
                if keycode:
                    logger.debug(f"Interception kullanarak tuş basılıyor: {key}")
                    self.tusbas(keycode, duration)
                else:
                    # Keycode bulunamadı, pyautogui kullan
                    logger.debug(f"PyAutoGUI kullanarak tuş basılıyor: {key}")
                    pyautogui.press(key)
            else:
                # Interception yoksa, pyautogui kullan
                logger.debug(f"PyAutoGUI kullanarak tuş basılıyor: {key}")
                pyautogui.press(key)
        except Exception as e:
            logger.error(f"Tuş basma işlemi başarısız: {e}")
    
    def tusbas(self, key, gecikme):
        """
        Belirlenen tuşa basma ve bırakma işlemini gerçekleştiren fonksiyon.
        
        Args:
            key (int): Basılacak tuşun keycode değeri
            gecikme (float): Tuşa basılı tutma süresi (saniye cinsinden)
        """
        if not interception_available or self.driver is None or self.keyboard is None:
            logger.error("Interception kullanılamıyor, tuş basılamadı.")
            return
            
        try:
            # Tuşa basma (key down) işlemi
            interception_press = key_stroke(key, interception_key_state.INTERCEPTION_KEY_DOWN.value, 0)
            self.driver.send(self.keyboard, interception_press)
            
            # Tuşa basılı tutma süresi
            time.sleep(gecikme)
            
            # Tuşu bırakma (key up) işlemi
            interception_press.state = interception_key_state.INTERCEPTION_KEY_UP.value
            self.driver.send(self.keyboard, interception_press)
            
            # İki tuş basma arasında minimum bekleme süresi (tuş bırakıldıktan sonra)
            time.sleep(0.01)  # 10ms
            
            logger.debug(f"Interception kullanarak tuş basma başarılı: {key}")
        except Exception as e:
            logger.error(f"Interception ile tuş basma hatası: {e}")


class MainWindow(QMainWindow):
    """Ana uygulama penceresi."""
    
    information_signal = pyqtSignal(str)
    
    def __init__(self):
        super(MainWindow, self).__init__()
        
        # Servisler
        self.screen_service = ScreenService()
        self.km_service = KeyboardMouseService()
        
        # HealHelper ve BuffHelper nesneleri
        self.heal_helper = HealHelper(
            click_func=self.km_service.click,
            key_press_func=self.km_service.press_key,
            screenshot_func=self.screen_service.take_screenshot,
            main_window=self  # Ana pencere referansını ekliyoruz
        )
        
        self.buff_helper = BuffHelper(
            key_press_func=self.km_service.press_key
        )
        
        # Özel ekran görüntüsü için değişken
        self.custom_screenshot = np.zeros((10, 10, 3), dtype=np.uint8)  # Boş 10x10 RGB görüntüsü
        
        # Koordinat alma işi için değişken
        self.auto_heal_target_job = 0
        
        # Tıklama koordinatı alma işi için değişken
        self.auto_heal_click_target_job = 0
        
        # Ayarlar dosyası
        self.config_file = "settings.ini"
        self.config = configparser.ConfigParser()
        
        # Klavye dinleyici için değişkenler
        self.pressed_keys = set()
        
        # UI
        self.setup_ui()
        
        # Sinyal bağlantıları
        self.information_signal.connect(self.update_status)
        
        # Klavye dinleyiciyi başlat
        self.start_key_listener()
        
        # Ayarları yükle
        self.load_config()
        
        # Debug klasörü
        self.debug_mode = False  # Debug modu varsayılan olarak kapalı
        if self.debug_mode:
            os.makedirs('images', exist_ok=True)
    
    def setup_ui(self):
        """Kullanıcı arayüzünü oluşturur."""
        self.setWindowTitle("Knight Online Otomatik İyileştirme & Buff Sistemi")
        self.setGeometry(100, 100, 800, 800)
        
        # Ana widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Ana layout
        main_layout = QVBoxLayout(central_widget)
        
        # Bilgi etiketi
        info_label = QLabel("Knight Online Otomatik İyileştirme & Buff Sistemi")
        info_label.setFont(QFont("Arial", 14, QFont.Bold))
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("color: #3498db; margin: 10px;")
        info_label.setToolTip("Knight Online oyunu için otomatik iyileştirme ve buff sistemi")
        main_layout.addWidget(info_label)
        
        # Auto Heal & Buff widget
        self.auto_heal_buff_widget = AutoHealBuffWidget(self)
        main_layout.addWidget(self.auto_heal_buff_widget)
        
        # Koordinat alma olaylarını bağla
        for i, row_widget in enumerate(self.auto_heal_buff_widget.heal_rows):
            row_widget.button.clicked.connect(lambda checked=False, idx=i: self.handle_take_coordinates(idx))
        
        # Başlat/Durdur butonları
        buttons_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Başlat")
        self.start_button.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 15px;")
        self.start_button.clicked.connect(self.start_auto_heal_buff)
        self.start_button.setToolTip("Otomatik iyileştirme ve buff sistemini başlat")
        self.start_button.setFixedHeight(50)
        
        self.stop_button = QPushButton("Durdur")
        self.stop_button.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 15px;")
        self.stop_button.clicked.connect(self.stop_auto_heal_buff)
        self.stop_button.setEnabled(False)
        self.stop_button.setToolTip("Otomatik iyileştirme ve buff sistemini durdur")
        self.stop_button.setFixedHeight(50)
        
        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.stop_button)
        
        main_layout.addLayout(buttons_layout)
        
        # Durum çubuğu
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Program hazır. Başlatmak için 'Başlat' butonuna tıklayın.")
        
        # Karanlık tema uygula
        self.apply_dark_theme()
    
    def apply_dark_theme(self):
        """Karanlık tema uygular."""
        dark_theme = """
        QWidget {
            background-color: #2E2E2E;
            color: #FFFFFF;
            font-size: 14px;
        }
        QLineEdit, QSpinBox, QComboBox {
            background-color: #3E3E3E;
            color: #FFFFFF;
            border: 1px solid #5A5A5A;
            border-radius: 4px;
            padding: 2px;
        }
        QPushButton {
            background-color: #3E3E3E;
            color: #FFFFFF;
            border: 1px solid #5A5A5A;
            border-radius: 4px;
            padding: 5px;
        }
        QPushButton:disabled {
            background-color: #2E2E2E;
            color: #AAAAAA;
        }
        QPushButton:hover {
            background-color: #5A5A5A;
        }
        QCheckBox, QLabel {
            color: #FFFFFF;
        }
        QGroupBox {
            border: 1px solid #5A5A5A;
            border-radius: 4px;
            margin-top: 10px;
        }
        QGroupBox::title {
            color: #3498db;
        }
        """
        self.setStyleSheet(dark_theme)
    
    def update_status(self, message):
        """Durum çubuğunu günceller."""
        self.status_bar.showMessage(message)
        logger.info(message)
    
    def start_auto_heal_buff(self):
        """Otomatik iyileştirme ve buff sistemini başlatır."""
        try:
            # Widget'tan veri al
            rows_data, heal_data, buffs_data = self.auto_heal_buff_widget.start_working()
            
            # Heal Helper'a verileri aktar
            # Heal ayarlarını aktar
            self.heal_helper.set_heal_percentage(self.auto_heal_buff_widget.heal_percentage)
            self.heal_helper.set_heal_key(heal_data["heal_key"])
            
            # Mass Heal ayarlarını aktar
            self.heal_helper.set_mass_heal_key(heal_data["mass_heal_key"])
            self.heal_helper.set_mass_heal_active(heal_data["mass_heal_active"])
            self.heal_helper.set_mass_heal_percentage(heal_data["mass_heal_percentage"])
            self.heal_helper.set_mass_heal_party_check(heal_data["mass_heal_party_check"])
            
            # Kontrol frekansını ayarla
            self.heal_helper.set_check_interval(self.auto_heal_buff_widget.heal_check_interval)
            
            # HP satırı verilerini aktar
            for i, row_data in enumerate(rows_data):
                self.heal_helper.set_row_active(i, row_data["active"])
                if row_data["coords"] and len(row_data["coords"]) == 4:
                    self.heal_helper.set_row_coordinates(i, row_data["coords"])
            
            # Buff Helper'a verileri aktar
            # Kontrol frekansını ayarla
            self.buff_helper.set_check_interval(self.auto_heal_buff_widget.buff_check_interval)
            
            # Buff ayarlarını aktar
            for buff_id, buff_info in buffs_data.items():
                if buff_id.isdigit():  # Sayısal ID'ler için
                    buff_idx = int(buff_id)
                    self.buff_helper.set_buff_active(buff_idx, buff_info["active"])
                    self.buff_helper.set_buff_key(buff_idx, buff_info["key"])
                    self.buff_helper.set_buff_duration(buff_idx, buff_info["duration"])
                    # Zamanlayıcıyı sıfırla
                    self.buff_helper.reset_buff_timer(buff_idx)
                    logger.info(f"Buff {buff_idx+1} ({buff_info['name']}) ayarlandı: {buff_info}")
            
            # Sistemleri başlat
            self.heal_helper.start()
            self.buff_helper.start()
            
            # UI'ı güncelle
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            
            self.information_signal.emit("Otomatik iyileştirme ve buff sistemi başlatıldı.")
            
        except Exception as e:
            logger.error(f"Sistem başlatılırken hata: {e}")
            QMessageBox.critical(self, "Hata", f"Sistem başlatılırken bir hata oluştu: {e}")
    
    def stop_auto_heal_buff(self):
        """Otomatik iyileştirme ve buff sistemini durdurur."""
        try:
            # Sistemleri durdur
            self.heal_helper.stop()
            self.buff_helper.stop()
            
            # Widget'ı güncelle
            self.auto_heal_buff_widget.stop_working()
            
            # UI'ı güncelle
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            
            self.information_signal.emit("Otomatik iyileştirme ve buff sistemi durduruldu.")
            
        except Exception as e:
            logger.error(f"Sistem durdurulurken hata: {e}")
            QMessageBox.critical(self, "Hata", f"Sistem durdurulurken bir hata oluştu: {e}")
    
    def load_config(self):
        """Ayarları yükler."""
        try:
            # Ayar dosyası var mı kontrol et
            if os.path.exists(self.config_file):
                self.config.read(self.config_file)
                
                # AutoHealBuffWidget için ayarları yükle
                if not self.config.has_section('AutoHealBuff'):
                    self.config.add_section('AutoHealBuff')
                
                self.auto_heal_buff_widget.load_config(self.config['AutoHealBuff'])
                
                self.information_signal.emit("Ayarlar başarıyla yüklendi.")
            else:
                # İlk kez çalıştırılıyorsa, yeni bir ayar dosyası oluştur
                self.save_config()
                
        except Exception as e:
            logger.error(f"Ayarlar yüklenirken hata: {e}")
            QMessageBox.warning(self, "Uyarı", f"Ayarlar yüklenirken bir hata oluştu: {e}")
    
    def save_config(self):
        """Ayarları kaydeder."""
        try:
            # Config dosyasını oluştur
            if not self.config.has_section('AutoHealBuff'):
                self.config.add_section('AutoHealBuff')
            
            # AutoHealBuffWidget ayarlarını kaydet
            self.config['AutoHealBuff'] = self.auto_heal_buff_widget.save_config(self.config['AutoHealBuff'])
            
            # Dosyaya yaz
            with open(self.config_file, 'w') as configfile:
                self.config.write(configfile)
            
            self.information_signal.emit("Ayarlar başarıyla kaydedildi.")
            
        except Exception as e:
            logger.error(f"Ayarlar kaydedilirken hata: {e}")
            QMessageBox.critical(self, "Hata", f"Ayarlar kaydedilirken bir hata oluştu: {e}")
    
    def closeEvent(self, event):
        """Uygulama kapatılırken çağrılır."""
        try:
            # Sistemleri durdur
            if hasattr(self, 'heal_helper') and hasattr(self.heal_helper, 'working') and self.heal_helper.working:
                self.heal_helper.stop()
            
            if hasattr(self, 'buff_helper') and hasattr(self.buff_helper, 'working') and self.buff_helper.working:
                self.buff_helper.stop()
            
            # Ayarları kaydet
            self.save_config()
            
            # Olay işlemi tamamlandı
            event.accept()
            
        except Exception as e:
            logger.error(f"Uygulama kapatılırken hata: {e}")
            event.accept()  # Yine de kapat
    
    def key_listener(self):
        """Klavye tuşlarını dinler ve işler."""
        self.pressed_keys = set()
        
        def on_press(key):
            if key in self.pressed_keys:
                return
                
            self.pressed_keys.add(key)
            
            # CTRL tuşu algılama
            if key == Key.ctrl_l or key == Key.ctrl_r:
                # HP barı koordinat alma işlemi aktif mi?
                if 100 <= self.auto_heal_target_job <= 107:
                    row = self.auto_heal_target_job - 100
                    # Fare konumunu al
                    x, y = pyautogui.position()
                    
                    logger.info(f"CTRL tuşu algılandı, koordinat alınıyor: ({x}, {y})")
                    
                    # Koordinatları ayarla
                    self.auto_heal_buff_widget.set_row_coordinates(row, x, y)
                    
                    # İlk nokta mı ikinci nokta mu kontrol et
                    coords = self.auto_heal_buff_widget.heal_rows[row].coords
                    if len(coords) == 4:  # İkinci nokta da alındı
                        self.auto_heal_target_job = 0  # İşlemi tamamla
                        logger.info(f"Satır {row+1} için koordinatlar tamamlandı: {coords}")
                        
                        # HealHelper'a koordinatları da aktar
                        self.heal_helper.set_row_coordinates(row, coords)
                        
                        # Kullanıcıya koordinatların tamamlandığını bildir
                        self.on_coordinate_captured(row, False)
                    else:  # İlk nokta alındı
                        logger.info(f"Satır {row+1} için ilk koordinat alındı: ({x}, {y})")
                        
                        # Kullanıcıya ilk noktanın alındığını bildir
                        self.on_coordinate_captured(row, True)
        
        def on_release(key):
            if key in self.pressed_keys:
                self.pressed_keys.remove(key)
        
        # Dinleyiciyi başlat
        listener = Listener(on_press=on_press, on_release=on_release)
        listener.start()
    
    def start_key_listener(self):
        """Klavye dinleyiciyi başlatan thread."""
        try:
            threading.Thread(target=self.key_listener, daemon=True).start()
            logger.info("Klavye dinleyici başlatıldı.")
        except Exception as e:
            logger.error(f"Klavye dinleyici başlatılamadı: {e}")
    
    def handle_take_coordinates(self, row_idx):
        """Koordinat alma butonuna tıklandığında çağrılır."""
        self.auto_heal_target_job = 100 + row_idx  # 100-107 arası özel job numaraları
        
        # Kullanıcıya bildiri göster
        message = f"{row_idx+1}. satır için HP barının SOL ve SAĞ koordinatlarını almak için iki kez CTRL tuşuna basın."
        self.information_signal.emit(message)
        
        # Popup ile daha görünür bildirim
        QMessageBox.information(self, 
                              "Koordinat Alma", 
                              f"{row_idx+1}. satır için HP barının koordinatlarını almak üzeresiniz.\n\n"
                              f"Lütfen şu adımları izleyin:\n"
                              f"1. HP barının SOL ucuna gelin ve CTRL tuşuna basın\n"
                              f"2. HP barının SAĞ ucuna gelin ve CTRL tuşuna basın\n\n"
                              f"İşlem tamamlandığında koordinatlar kaydedilecektir.")
        
        # Auto Heal ve Buff widget'taki koordinat alma metodunu çağır
        if hasattr(self.auto_heal_buff_widget, 'take_row_coordinates'):
            self.auto_heal_buff_widget.take_row_coordinates(row_idx)
    
    def on_coordinate_captured(self, row_idx, is_first_point):
        """Koordinat yakalandığında çağrılır."""
        if is_first_point:
            message = f"{row_idx+1}. satır için SOL koordinat alındı. Şimdi SAĞ koordinat için CTRL tuşuna basın."
            logger.info(message)
        else:
            message = f"{row_idx+1}. satır için tüm koordinatlar alındı. Koordinatlar kaydedildi."
            logger.info(message)
            
        self.information_signal.emit(message)


if __name__ == "__main__":
    try:
        # PyQt uygulamasını başlat
        app = QApplication(sys.argv)
        
        # Ana pencereyi oluştur ve göster
        window = MainWindow()
        window.show()
        
        # Uygulamayı çalıştır
        sys.exit(app.exec_())
        
    except Exception as e:
        logger.critical(f"Uygulama başlatılırken kritik hata: {e}")
        print(f"Kritik hata: {e}") 