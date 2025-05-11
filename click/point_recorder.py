#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Fare Kaydedici (Mouse Recorder) Uygulaması

Bu uygulama, fare tıklamalarını kaydeder ve daha sonra aynı tıklamaları 
otomatik olarak tekrar edebilir. PyQt5 tabanlı bir grafik arayüzü kullanır 
ve Windows API'leri aracılığıyla gerçek donanım seviyesinde fare tıklamaları yapar.

Temel Özellikler:
- Sol ve sağ fare tıklamalarını kaydetme
- Tıklamalar arasındaki gecikmeleri kaydetme
- Kaydedilen tıklamaları otomatik olarak tekrarlama
- Tıklama serilerini profil olarak saklama ve yükleme
- Klavye kısayolları ile kolay kullanım

Geliştirici: Fare Kaydedici Ekibi
Versiyon: 0.3
Lisans: MIT
"""

import sys
import time
import threading
import pyautogui
import keyboard
import warnings
import win32api
import win32con
import datetime
import configparser
import os
import json

# PyQt5 uyarılarını bastır
warnings.filterwarnings("ignore", category=DeprecationWarning)

from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                           QWidget, QLabel, QHBoxLayout, QMessageBox, QCheckBox,
                           QListWidget, QScrollArea, QLineEdit)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QTimer, QEvent

# PyAutoGUI failsafe özelliğini devre dışı bırak
# DİKKAT: Bu mod, programın control+alt+del gibi normal durdurma mekanizmalarını devre dışı bırakır
pyautogui.FAILSAFE = False

# Klavye olaylarını işlemek için sinyal sınıfı
class KeyboardSignals(QObject):
    """
    Klavye kısayollarını yakalayıp sinyal olarak ileten sınıf.
    PyQt5 sinyal mekanizması kullanılarak klavye olaylarını uygulama içinde iletir.
    """
    key_c_pressed = pyqtSignal()  # C tuşu - Oynat sinyali
    key_b_pressed = pyqtSignal()  # B tuşu - Kaydı Durdur sinyali
    key_k_pressed = pyqtSignal()  # K tuşu - Kaydı Başlat sinyali
    esc_pressed = pyqtSignal()    # ESC tuşu - Durdur sinyali

# Fare olaylarını izlemek için sınıf
class MouseListener(QObject):
    """
    Fare tıklamalarını dinleyen ve sinyaller yayınlayan sınıf.
    
    Win32API kullanarak düşük seviyede fare olaylarını yakalar ve bu olayları
    PyQt5 sinyalleri olarak iletir. Ayrı bir iş parçacığında çalışarak
    uygulamanın ana arayüzünü bloke etmeden sürekli fare durumunu kontrol eder.
    
    Sinyaller:
        left_click(int, int): Sol tıklama algılandığında x, y koordinatlarını iletir
        right_click(int, int): Sağ tıklama algılandığında x, y koordinatlarını iletir
    """
    left_click = pyqtSignal(int, int)
    right_click = pyqtSignal(int, int)
    
    def __init__(self):
        """
        MouseListener sınıfının yapıcı metodu.
        Dinleme durumunu ve thread'i başlatır.
        """
        super().__init__()
        self.is_listening = False  # Dinleme durumu
        self.thread = None  # Dinleme iş parçacığı
    
    def start_listening(self):
        """
        Fare dinlemeyi başlatır.
        
        Eğer dinleme zaten aktifse, işlem yapmaz.
        Değilse, yeni bir iş parçacığında dinleme döngüsünü başlatır.
        """
        if self.is_listening:
            return
            
        self.is_listening = True
        self.thread = threading.Thread(target=self._listen_mouse, daemon=True)
        self.thread.start()
        print("Fare dinleme başladı")
    
    def stop_listening(self):
        """
        Fare dinlemeyi durdurur.
        
        Dinleme durumunu False yaparak _listen_mouse döngüsünün sonlanmasını sağlar
        ve thread'in güvenli bir şekilde sonlanmasını bekler.
        """
        self.is_listening = False
        if self.thread and self.thread.is_alive():
            self.thread.join(1.0)  # En fazla 1 saniye bekle
        print("Fare dinleme durduruldu")
    
    def _listen_mouse(self):
        """
        Fare tıklamalarını dinleyen ana döngü.
        
        Bu metot ayrı bir iş parçacığında çalışır ve sürekli olarak fare durumunu kontrol eder.
        Sol veya sağ fare tuşlarına basıldığında ilgili sinyalleri yayınlar.
        Çift tıklama sorununu önlemek için durum değişkenlerini kullanır.
        """
        # Sol ve sağ fare tuşları durumları
        left_button_state = False
        right_button_state = False
        
        while self.is_listening:
            try:
                # Sol fare tuşu kontrolü
                if win32api.GetAsyncKeyState(win32con.VK_LBUTTON) < 0:
                    if not left_button_state:
                        x, y = win32api.GetCursorPos()
                        print(f"Sol tıklama algılandı: X:{x}, Y:{y}")
                        self.left_click.emit(x, y)
                        left_button_state = True
                else:
                    left_button_state = False
                
                # Sağ fare tuşu kontrolü
                if win32api.GetAsyncKeyState(win32con.VK_RBUTTON) < 0:
                    if not right_button_state:
                        x, y = win32api.GetCursorPos()
                        print(f"Sağ tıklama algılandı: X:{x}, Y:{y}")
                        self.right_click.emit(x, y)
                        right_button_state = True
                else:
                    right_button_state = False
                
                # Çok hızlı CPU kullanımını önlemek için kısa bekleme
                time.sleep(0.05)
                
            except Exception as e:
                print(f"Fare dinleme hatası: {e}")
                time.sleep(0.5)  # Hata durumunda daha uzun bekle

# Özel olay sınıfı
class StatusUpdateEvent(QEvent):
    """
    Durum güncellemeleri için özel bir QEvent sınıfı.
    
    Ana uygulama thread'i dışındaki thread'lerden durum güncellemesi 
    göndermek için kullanılır. Bu, farklı thread'ler arasında
    güvenli iletişim sağlar.
    """
    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())
    
    def __init__(self):
        """
        StatusUpdateEvent yapıcı metodu.
        Özel olay tipini kullanarak yeni bir olay oluşturur.
        """
        super(StatusUpdateEvent, self).__init__(self.EVENT_TYPE)

# Otomatik kapanan mesaj kutusu sınıfı
class AutoCloseMessageBox(QMessageBox):
    """
    Belirli bir süre sonra otomatik olarak kapanan mesaj kutusu.
    
    Kullanıcı etkileşimi gerektirmeyen bildirimler için kullanılır.
    Belirlenen süre sonunda otomatik olarak kapanır.
    """
    def __init__(self, *args, **kwargs):
        """
        AutoCloseMessageBox yapıcı metodu.
        
        QMessageBox'tan miras alır ve ek olarak bir zamanlayıcı ekler.
        Zamanlayıcı, belirlenen süre sonunda mesaj kutusunu otomatik olarak kapatır.
        """
        super(AutoCloseMessageBox, self).__init__(*args, **kwargs)
        # 2 saniye sonra kapanacak timer oluştur
        self.timeout = 2  # saniye
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.close)
        self.timer.start(self.timeout * 1000)  # ms cinsinden
        
        # Timer'ın kalan süresini göster
        self.countdown_label = QLabel(f"Bu mesaj {self.timeout} saniye sonra kapanacak", self)
        self.countdown_label.setAlignment(Qt.AlignCenter)
        self.layout().addWidget(self.countdown_label, self.layout().rowCount(), 0, 1, self.layout().columnCount())

# Sağ tıklama fonksiyonu (win32api kullanarak)
def rightclick(x, y):
    """
    Belirtilen koordinatlarda sağ fare tıklaması gerçekleştirir.
    
    Win32API kullanarak donanım düzeyinde gerçek bir sağ fare tıklaması yapar.
    Bu, daha güvenilir ve sistem genelinde çalışabilen bir tıklama sağlar.
    
    Args:
        x (int): Tıklama yapılacak x koordinatı
        y (int): Tıklama yapılacak y koordinatı
        
    Returns:
        bool: İşlem başarılıysa True, değilse False
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
        print(f"Sağ tıklama yapıldı: X:{x}, Y:{y}")
        return True
    except Exception as e:
        print(f"Sağ tıklama hatası: {e}")
        return False

# Sol tıklama fonksiyonu (win32api kullanarak)
def leftclick(x, y):
    """
    Belirtilen koordinatlarda sol fare tıklaması gerçekleştirir.
    
    Win32API kullanarak donanım düzeyinde gerçek bir sol fare tıklaması yapar.
    Bu, daha güvenilir ve sistem genelinde çalışabilen bir tıklama sağlar.
    
    Args:
        x (int): Tıklama yapılacak x koordinatı
        y (int): Tıklama yapılacak y koordinatı
        
    Returns:
        bool: İşlem başarılıysa True, değilse False
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
        print(f"Sol tıklama yapıldı: X:{x}, Y:{y}")
        return True
    except Exception as e:
        print(f"Sol tıklama hatası: {e}")
        return False

# Otomatik kapanan bilgi mesajı göster
def show_auto_close_info(parent, title, message):
    """
    Otomatik kapanan bilgi mesajı gösterir.
    
    Args:
        parent: Ebeveyn pencere
        title (str): Mesaj kutusu başlığı
        message (str): Görüntülenecek mesaj
    """
    msg_box = AutoCloseMessageBox(QMessageBox.Information, title, message, QMessageBox.Ok, parent)
    msg_box.exec_()
    
# Otomatik kapanan uyarı mesajı göster
def show_auto_close_warning(parent, title, message):
    """
    Otomatik kapanan uyarı mesajı gösterir.
    
    Args:
        parent: Ebeveyn pencere
        title (str): Mesaj kutusu başlığı
        message (str): Görüntülenecek mesaj
    """
    msg_box = AutoCloseMessageBox(QMessageBox.Warning, title, message, QMessageBox.Ok, parent)
    msg_box.exec_()

# Tıklama türünü temsil eden sınıf
class ClickAction:
    """
    Bir fare tıklamasını temsil eden veri sınıfı.
    
    Her fare tıklaması için konum, tür, zaman damgası ve gecikme bilgilerini saklar.
    Bu bilgiler daha sonra tıklamaları tekrar oynatmak için kullanılır.
    """
    def __init__(self, x, y, is_right_click=False, timestamp=None, delay_after=0):
        """
        ClickAction yapıcı metodu.
        
        Args:
            x (int): Tıklama x koordinatı
            y (int): Tıklama y koordinatı
            is_right_click (bool): True ise sağ tıklama, False ise sol tıklama
            timestamp (datetime): Tıklama zamanı (None ise şu anki zaman kullanılır)
            delay_after (int): Bu tıklamadan sonraki bekleme süresi (ms)
        """
        self.x = x
        self.y = y
        self.is_right_click = is_right_click  # True=Sağ tıklama, False=Sol tıklama
        self.timestamp = timestamp or datetime.datetime.now()
        self.delay_after = delay_after  # Bu tıklamadan sonraki bekleme süresi (ms)
    
    def __str__(self):
        """
        ClickAction nesnesinin metin temsili.
        
        Returns:
            str: Tıklama bilgilerini içeren metin
        """
        click_type = "Sağ Tık" if self.is_right_click else "Sol Tık"
        delay_info = f"Gecikme: {self.delay_after}ms" if self.delay_after > 0 else ""
        return f"{click_type} - X:{self.x}, Y:{self.y} - {self.timestamp.strftime('%H:%M:%S.%f')[:-3]} {delay_info}"

# INI dosyasının varsayılan konumu
CONFIG_FILE = "settings.ini"

# ClickAction sınıfını JSON formatına dönüştürme
def click_action_to_dict(action):
    """
    ClickAction nesnesini sözlük yapısına dönüştürür.
    
    Bu fonksiyon, ClickAction nesnelerini JSON formatında saklamak için
    serileştirme işlemi yapar.
    
    Args:
        action (ClickAction): Dönüştürülecek tıklama nesnesi
        
    Returns:
        dict: Tıklama nesnesinin sözlük temsili
    """
    return {
        'x': action.x,
        'y': action.y,
        'is_right_click': action.is_right_click,
        'timestamp': action.timestamp.isoformat(),
        'delay_after': action.delay_after
    }

# JSON formatından ClickAction oluşturma
def dict_to_click_action(data):
    """
    Sözlük yapısından ClickAction nesnesi oluşturur.
    
    JSON formatından alınan verileri kullanarak ClickAction nesnesi
    oluşturur. Bu, kaydedilmiş profilleri tekrar yüklerken kullanılır.
    
    Args:
        data (dict): ClickAction verilerini içeren sözlük
        
    Returns:
        ClickAction: Oluşturulan tıklama nesnesi
    """
    return ClickAction(
        x=data['x'],
        y=data['y'],
        is_right_click=data['is_right_click'],
        timestamp=datetime.datetime.fromisoformat(data['timestamp']),
        delay_after=data['delay_after']
    )

class PointRecorderApp(QMainWindow):
    """
    Mouse tıklamalarını kaydeden ve oynatan ana uygulama sınıfı.
    
    Bu sınıf, uygulamanın ana yapısını, kullanıcı arayüzünü ve tüm
    işlevselliğini yönetir. Tıklama kaydetme, oynatma ve profil
    yönetimi işlemleri burada gerçekleştirilir.
    """
    def __init__(self):
        """
        PointRecorderApp sınıfının yapıcı metodu.
        
        Uygulama durumu değişkenlerini, fare dinleyiciyi, klavye dinleyiciyi 
        başlatır ve kullanıcı arayüzünü oluşturur.
        """
        super().__init__()
        
        # Uygulama durumu
        self.click_actions = []  # ClickAction nesneleri listesi
        self.is_recording = False
        self.is_playing = False
        self.playback_thread = None
        self.repeat_playback = False  # Tekrarlama seçeneği
        self.last_click_time = None   # Son tıklama zamanı
        self.use_recorded_delays = True  # Kaydedilen gecikmeleri kullan
        self.current_profile_name = "default"  # Varsayılan profil adı
        
        # Fare dinleyici
        self.mouse_listener = MouseListener()
        self.mouse_listener.left_click.connect(self.on_left_click)
        self.mouse_listener.right_click.connect(self.on_right_click)
        
        # Klavye sinyalleri
        self.keyboard_signals = KeyboardSignals()
        self.keyboard_signals.key_c_pressed.connect(self.on_key_c_pressed)
        self.keyboard_signals.key_b_pressed.connect(self.on_key_b_pressed)
        self.keyboard_signals.key_k_pressed.connect(self.on_key_k_pressed)
        self.keyboard_signals.esc_pressed.connect(self.on_esc_pressed)
        
        # Klavye olaylarını izleme için son tuş basma zamanları
        self.last_key_c_press = 0
        self.last_key_b_press = 0
        self.last_key_k_press = 0
        self.last_esc_press = 0
        
        # Arayüz
        self.init_ui()
        
        # Klavye izleme için timer başlat
        self.start_keyboard_timer()
        
        # Son profili yüklemeyi dene
        try:
            self.load_settings()
        except Exception as e:
            print(f"Ayarlar yüklenirken hata oluştu: {e}")
            # İlk kullanımda hata olmasın diye sessizce devam et
    
    def init_ui(self):
        """
        Kullanıcı arayüzünü oluşturur.
        
        Tüm arayüz bileşenlerini (butonlar, etiketler, listeler vb.) oluşturur,
        yerleşimlerini ayarlar ve sinyal-slot bağlantılarını kurar.
        """
        self.setWindowTitle("Fare Kaydedici v0.3")
        self.setGeometry(100, 100, 550, 650)
        
        # Ana widget ve layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QVBoxLayout()
        self.central_widget.setLayout(self.main_layout)
        
        # Durum etiketi
        self.status_label = QLabel("Hazır - Kaydetmek için 'Tıklamaları Kaydet' butonuna basın")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.status_label)
        
        # Koordinat bilgisi
        self.coordinates_label = QLabel("Kaydedilen tıklama sayısı: 0")
        self.coordinates_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.coordinates_label)
        
        # Profil bilgisi
        self.profile_label = QLabel(f"Aktif Profil: {self.current_profile_name}")
        self.profile_label.setAlignment(Qt.AlignCenter)
        font = self.profile_label.font()
        font.setBold(True)
        self.profile_label.setFont(font)
        self.main_layout.addWidget(self.profile_label)
        
        # Kısayol açıklaması
        keyboard_shortcuts_label = QLabel(
            "Klavye Kısayolları:\n"
            "K - Kaydı Başlat\n"
            "B - Kaydı Durdur\n"
            "C - Oynat\n"
            "ESC - Durdur"
        )
        keyboard_shortcuts_label.setStyleSheet("color: #666; font-size: 10px;")
        self.main_layout.addWidget(keyboard_shortcuts_label)
        
        # Bir boşluk ekle
        self.main_layout.addSpacing(10)
        
        # Kayıt butonları
        self.record_layout = QHBoxLayout()
        
        # Kayıt başlat butonu
        self.record_button = QPushButton("Tıklamaları Kaydet")
        self.record_button.setMinimumHeight(40)
        self.record_button.clicked.connect(self.start_recording)
        self.record_layout.addWidget(self.record_button)
        
        # Kayıt durdurma butonu
        self.stop_record_button = QPushButton("Kaydı Durdur (B)")
        self.stop_record_button.setMinimumHeight(40)
        self.stop_record_button.clicked.connect(self.stop_recording)
        self.record_layout.addWidget(self.stop_record_button)
        
        self.main_layout.addLayout(self.record_layout)
        
        # Tıklama listesi
        self.click_list_label = QLabel("Kaydedilen Tıklamalar:")
        self.click_list_label.setAlignment(Qt.AlignLeft)
        self.main_layout.addWidget(self.click_list_label)
        
        self.click_list = QListWidget()
        self.click_list.setMinimumHeight(150)
        self.main_layout.addWidget(self.click_list)
        
        # Bir boşluk ekle
        self.main_layout.addSpacing(10)
        
        # Dosya İşlemleri Grubu
        self.file_group_label = QLabel("Profil İşlemleri:")
        self.file_group_label.setAlignment(Qt.AlignLeft)
        self.main_layout.addWidget(self.file_group_label)
        
        # Profil adı giriş alanı
        self.profile_layout = QHBoxLayout()
        self.profile_name_label = QLabel("Profil Adı:")
        self.profile_name_input = QLineEdit(self.current_profile_name)
        self.profile_layout.addWidget(self.profile_name_label)
        self.profile_layout.addWidget(self.profile_name_input)
        self.main_layout.addLayout(self.profile_layout)
        
        # Dosya işlem butonları
        self.file_buttons_layout = QHBoxLayout()
        
        # Kaydet butonu
        self.save_button = QPushButton("Kaydet")
        self.save_button.clicked.connect(self.save_profile)
        self.file_buttons_layout.addWidget(self.save_button)
        
        # Yükle butonu
        self.load_button = QPushButton("Yükle")
        self.load_button.clicked.connect(self.load_profile)
        self.file_buttons_layout.addWidget(self.load_button)
        
        # Sıfırla butonu
        self.reset_button = QPushButton("Sıfırla")
        self.reset_button.clicked.connect(self.reset_recording)
        self.file_buttons_layout.addWidget(self.reset_button)
        
        self.main_layout.addLayout(self.file_buttons_layout)
        
        # Bir boşluk ekle
        self.main_layout.addSpacing(10)
        
        # Oynatma Seçenekleri grubu
        self.options_label = QLabel("Oynatma Seçenekleri:")
        self.options_label.setAlignment(Qt.AlignLeft)
        self.main_layout.addWidget(self.options_label)
        
        # Seçenek düzeni
        self.options_layout = QVBoxLayout()
        
        # Tekrar seçeneği
        self.repeat_checkbox = QCheckBox("Sürekli tekrarla")
        self.repeat_checkbox.setChecked(False)
        self.repeat_checkbox.stateChanged.connect(self.toggle_repeat)
        self.options_layout.addWidget(self.repeat_checkbox)
        
        # Kaydedilen gecikmeleri kullanma seçeneği
        self.use_delays_checkbox = QCheckBox("Kaydedilen tıklama gecikmelerini kullan")
        self.use_delays_checkbox.setChecked(True)
        self.use_delays_checkbox.stateChanged.connect(self.toggle_use_delays)
        self.options_layout.addWidget(self.use_delays_checkbox)
        
        self.main_layout.addLayout(self.options_layout)
        
        # Bir boşluk ekle
        self.main_layout.addSpacing(10)
        
        # Oynatma butonları
        self.buttons_layout = QHBoxLayout()
        
        # Oynat butonu
        self.play_button = QPushButton("Oynat (C)")
        self.play_button.setMinimumHeight(40)
        self.play_button.clicked.connect(self.start_playback)
        self.buttons_layout.addWidget(self.play_button)
        
        # Durdur butonu
        self.stop_button = QPushButton("Durdur (ESC)")
        self.stop_button.setMinimumHeight(40)
        self.stop_button.clicked.connect(self.stop_playback)
        self.buttons_layout.addWidget(self.stop_button)
        
        self.main_layout.addLayout(self.buttons_layout)
        
        # Tıklama açıklaması
        self.click_label = QLabel("Program kaydedilen konumlarda Sol/Sağ tıklama yapar")
        self.click_label.setAlignment(Qt.AlignCenter)
        font = self.click_label.font()
        font.setBold(True)
        self.click_label.setFont(font)
        self.main_layout.addWidget(self.click_label)
        
        # Versiyon bilgisi
        self.version_label = QLabel("v0.3 - Profil kaydetme ve yükleme özelliği eklendi")
        self.version_label.setAlignment(Qt.AlignRight)
        self.main_layout.addWidget(self.version_label)
    
    def toggle_repeat(self, state):
        """
        Tekrarlama seçeneğini açıp kapatır
        """
        self.repeat_playback = state == Qt.Checked
        print(f"Tekrarlama {'açık' if self.repeat_playback else 'kapalı'}")
    
    def start_keyboard_timer(self):
        """
        Klavye tuşlarını kontrol etmek için timer başlatır
        """
        self.keyboard_timer = QTimer(self)
        self.keyboard_timer.timeout.connect(self.check_keyboard)
        self.keyboard_timer.start(100)  # 100ms aralıklarla kontrol et
    
    def check_keyboard(self):
        """
        Klavye tuşlarını kontrol eder ve sinyalleri yayınlar
        """
        try:
            current_time = time.time()
            
            # B tuşu kontrolü (Kaydı Durdur)
            if keyboard.is_pressed('b'):
                if current_time - self.last_key_b_press > 0.5:
                    self.last_key_b_press = current_time
                    self.keyboard_signals.key_b_pressed.emit()
            
            # C tuşu kontrolü (Oynat)
            if keyboard.is_pressed('c'):
                if current_time - self.last_key_c_press > 0.5:
                    self.last_key_c_press = current_time
                    self.keyboard_signals.key_c_pressed.emit()
            
            # K tuşu kontrolü (Kaydı Başlat)
            if keyboard.is_pressed('k'):
                if current_time - self.last_key_k_press > 0.5:
                    self.last_key_k_press = current_time
                    self.keyboard_signals.key_k_pressed.emit()
            
            # ESC tuşu kontrolü (Durdur)
            if keyboard.is_pressed('esc'):
                if current_time - self.last_esc_press > 0.5:
                    self.last_esc_press = current_time
                    self.keyboard_signals.esc_pressed.emit()
        
        except Exception as e:
            print(f"Klavye kontrol hatası: {e}")
    
    def on_left_click(self, x, y):
        """
        Sol tıklama yakalandığında çağrılır
        """
        if self.is_recording:
            # Zaman damgası oluştur
            current_time = datetime.datetime.now()
            
            # Eğer daha önce bir tıklama varsa, aradaki gecikmeyi hesapla
            delay_after = 0
            if self.last_click_time:
                delay_after = int((current_time - self.last_click_time).total_seconds() * 1000)
            
            # Son tıklama zamanını güncelle
            self.last_click_time = current_time
            
            # Eğer bu ilk tıklama değilse, önceki tıklamanın gecikme süresini ayarla
            if len(self.click_actions) > 0:
                self.click_actions[-1].delay_after = delay_after
                # Liste görünümünü güncelle
                self.update_click_list()
            
            # Yeni tıklamayı kaydet
            click_action = ClickAction(x, y, is_right_click=False, timestamp=current_time)
            self.click_actions.append(click_action)
            print(f"Sol tıklama kaydedildi: X:{x}, Y:{y}, Önceki tıklamadan gecikme: {delay_after}ms")
            
            self.update_click_list()
            self.update_status()
    
    def on_right_click(self, x, y):
        """
        Sağ tıklama yakalandığında çağrılır
        """
        if self.is_recording:
            # Zaman damgası oluştur
            current_time = datetime.datetime.now()
            
            # Eğer daha önce bir tıklama varsa, aradaki gecikmeyi hesapla
            delay_after = 0
            if self.last_click_time:
                delay_after = int((current_time - self.last_click_time).total_seconds() * 1000)
            
            # Son tıklama zamanını güncelle
            self.last_click_time = current_time
            
            # Eğer bu ilk tıklama değilse, önceki tıklamanın gecikme süresini ayarla
            if len(self.click_actions) > 0:
                self.click_actions[-1].delay_after = delay_after
                # Liste görünümünü güncelle
                self.update_click_list()
            
            # Yeni tıklamayı kaydet
            click_action = ClickAction(x, y, is_right_click=True, timestamp=current_time)
            self.click_actions.append(click_action)
            print(f"Sağ tıklama kaydedildi: X:{x}, Y:{y}, Önceki tıklamadan gecikme: {delay_after}ms")
            
            self.update_click_list()
            self.update_status()
    
    @pyqtSlot()
    def on_key_c_pressed(self):
        """
        C tuşuna basılınca çağrılır - Oynatma başlatır
        """
        print("C tuşuna basıldı, oynatma başlatılıyor")
        self.start_playback()
    
    @pyqtSlot()
    def on_key_b_pressed(self):
        """
        B tuşuna basılınca çağrılır - Kaydı durdurur
        """
        print("B tuşuna basıldı, kayıt durduruluyor")
        self.stop_recording()
    
    @pyqtSlot()
    def on_key_k_pressed(self):
        """
        K tuşuna basılınca çağrılır - Kaydı başlatır
        """
        print("K tuşuna basıldı, kayıt başlatılıyor")
        self.start_recording()
    
    @pyqtSlot()
    def on_esc_pressed(self):
        """
        ESC tuşuna basılınca çağrılır - Oynatma veya kaydı durdurur
        """
        if self.is_playing:
            print("ESC tuşuna basıldı, oynatma durduruldu")
            self.stop_playback()
        elif self.is_recording:
            print("ESC tuşuna basıldı, kayıt durduruldu")
            self.stop_recording()
    
    def start_recording(self):
        """
        Fare tıklamalarını kaydetmeye başlar
        """
        if self.is_recording or self.is_playing:
            return
        
        # Kayıt modunu başlat
        self.is_recording = True
        self.last_click_time = None  # Son tıklama zamanını sıfırla
        self.status_label.setText("Kayıt yapılıyor... (Durdurmak için 'B' tuşuna basın)")
        
        # Buton durumlarını güncelle
        self.record_button.setEnabled(False)
        self.stop_record_button.setEnabled(True)
        self.play_button.setEnabled(False)
        
        # Fare dinleme başlat
        self.mouse_listener.start_listening()
        
        # Kullanıcıya bilgilendirme mesajı
        show_auto_close_info(self, "Kayıt Başladı", 
                           "Fare tıklamaları kaydediliyor...\n\n"
                           "Her sağ ve sol tıklama ve tıklamalar arasındaki gecikmeler kaydedilecek.\n\n"
                           "Kayıt durdurmak için 'B' tuşuna basın veya 'Kaydı Durdur' düğmesine tıklayın.")
    
    def stop_recording(self):
        """
        Fare tıklamalarını kaydetmeyi durdurur
        """
        if not self.is_recording:
            return
            
        # Kayıt modunu durdur
        self.is_recording = False
        self.last_click_time = None  # Son tıklama zamanını sıfırla
        self.status_label.setText("Kayıt tamamlandı - Oynat'a basabilirsiniz")
        
        # Fare dinleme durdur
        self.mouse_listener.stop_listening()
        
        # Kullanıcıya bilgilendirme mesajı
        if len(self.click_actions) > 0:
            # Son tıklamanın gecikme bilgisini gösterme
            if len(self.click_actions) > 0:
                self.click_actions[-1].delay_after = 0
                self.update_click_list()
                
            show_auto_close_info(self, "Kayıt Tamamlandı", 
                               f"Toplam {len(self.click_actions)} tıklama ve aralarındaki gecikmeler kaydedildi.\n\n"
                               "Oynatmak için 'C' tuşuna basın veya 'Oynat' düğmesine tıklayın.")
        else:
            show_auto_close_warning(self, "Uyarı", 
                                  "Hiç tıklama kaydedilmedi!\n\n"
                                  "Tekrar kaydetmeyi deneyin.")
    
    def update_click_list(self):
        """
        Tıklama listesini günceller
        """
        self.click_list.clear()
        for i, action in enumerate(self.click_actions):
            self.click_list.addItem(f"{i+1}. {action}")
    
    def update_status(self):
        """
        Arayüz durumunu günceller
        """
        self.coordinates_label.setText(f"Kaydedilen tıklama sayısı: {len(self.click_actions)}")
    
    def start_playback(self):
        """
        Kaydedilen tıklamaları oynatmaya başlar
        """
        # Geçerli tıklama kontrolü
        if len(self.click_actions) == 0:
            show_auto_close_warning(self, "Uyarı", "Oynatmak için önce tıklama kaydetmelisiniz!")
            return
        
        if self.is_playing or self.is_recording:
            return
        
        self.is_playing = True
        
        delay_info = "gerçek gecikmelerle" if self.use_recorded_delays else "sabit gecikmeli"
        tekrar_metni = "tekrarlı" if self.repeat_playback else "bir kez"
        self.status_label.setText(f"Oynatılıyor... ({tekrar_metni}, {delay_info})")
        
        # Kullanıcıya bilgilendirme mesajı (otomatik kapanan)
        show_auto_close_info(self, "Oynatma Başladı", 
                           f"{len(self.click_actions)} tıklama sırayla yapılacak.\n\n"
                           f"Oynatma modu: {'Tekrarlı' if self.repeat_playback else 'Tek sefer'}\n\n"
                           f"Gecikmeler: {'Kaydedilen orijinal gecikmeler' if self.use_recorded_delays else 'Sabit 250ms'}\n\n"
                           "Durdurmak için 'Durdur' düğmesine veya ESC tuşuna basın.")
        
        # Oynatma thread'ini başlat
        self.playback_thread = threading.Thread(target=self.play_actions, daemon=True)
        self.playback_thread.start()
    
    def play_actions(self):
        """
        Kaydedilen tıklamaları oynatır
        """
        try:
            # Tekrarlı veya tek seferlik oynatma
            do_repeat = self.repeat_playback
            
            while self.is_playing:
                for i, action in enumerate(self.click_actions):
                    if not self.is_playing:
                        break
                    
                    try:
                        print(f"Tıklama {i+1} yapılıyor: {'Sağ' if action.is_right_click else 'Sol'} tıklama ({action.x}, {action.y})")
                        
                        # Tıklama tipine göre fonksiyon seç
                        if action.is_right_click:
                            success = rightclick(action.x, action.y)
                        else:
                            success = leftclick(action.x, action.y)
                        
                        if not success:
                            print(f"Tıklama {i+1} başarısız oldu")
                        
                        # İşlemler arası bekleme - ya kaydedilen gecikme ya da sabit değer
                        if self.use_recorded_delays and i < len(self.click_actions) - 1:
                            delay = action.delay_after
                            if delay > 0:
                                print(f"Kaydedilen gecikme: {delay}ms bekleniyor")
                                time.sleep(delay / 1000.0)  # ms'yi saniyeye çevir
                            else:
                                # Eğer gecikme 0 ise minimum bekleme yap
                                time.sleep(0.05)
                        else:
                            # Sabit gecikme kullan
                            time.sleep(0.25)  # 250ms
                    except Exception as e:
                        print(f"Tıklama {i+1} hatası: {e}")
                
                # Tekrarlama seçeneği kontrol edilir
                if not do_repeat:
                    print("Tek seferlik oynatma tamamlandı")
                    self.is_playing = False
                    # Ana thread'de durum güncelleme
                    try:
                        QApplication.instance().postEvent(self, StatusUpdateEvent())
                    except Exception as e:
                        print(f"Durum güncelleme hatası: {e}")
                    break
                
                # Tekrarlama durumunda bir sonraki döngüye geçmeden önce biraz bekle
                time.sleep(0.5)
                
        except Exception as e:
            print(f"Oynatma hatası: {e}")
            self.is_playing = False
    
    # Olay işleme (Event processing)
    def event(self, event):
        """
        Özel olay işleme
        """
        if event.type() == StatusUpdateEvent.EVENT_TYPE:
            self.status_label.setText("Oynatma tamamlandı")
            return True
        return super().event(event)
    
    def stop_playback(self):
        """
        Oynatma işlemini durdurur
        """
        if self.is_playing:
            self.is_playing = False
            self.status_label.setText("Oynatma durduruldu")
            print("Tıklama işlemi durduruldu")
    
    def reset_recording(self):
        """
        Kaydedilen tıklamaları temizler
        """
        if self.is_recording or self.is_playing:
            show_auto_close_warning(self, "Uyarı", "Kayıt veya oynatma devam ederken sıfırlama yapılamaz!")
            return
            
        if not self.click_actions:
            return  # Zaten boşsa bir şey yapma
            
        result = QMessageBox.question(self, "Sıfırlama Onayı", 
                                     "Tüm tıklama kayıtları silinecek. Emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No)
        if result == QMessageBox.No:
            return
            
        self.click_actions = []
        self.is_playing = False
        self.is_recording = False
        self.update_click_list()
        self.update_status()
        
        self.status_label.setText("Tüm tıklama kayıtları silindi")
        show_auto_close_info(self, "Sıfırlama Tamamlandı", "Tüm tıklama kayıtları silindi.")

    def toggle_use_delays(self, state):
        """
        Kaydedilen gecikmeleri kullanma seçeneğini açıp kapatır
        """
        self.use_recorded_delays = state == Qt.Checked
        print(f"Kaydedilen gecikmeler {'kullanılacak' if self.use_recorded_delays else 'kullanılmayacak'}")

    def save_settings(self, profile_name=None):
        """
        Tıklama verilerini ve ayarları INI dosyasına kaydeder
        """
        try:
            config = configparser.ConfigParser()
            
            # Mevcut INI dosyasını oku (varsa)
            if os.path.exists(CONFIG_FILE):
                config.read(CONFIG_FILE)
                
            # Profil adını ayarla
            if profile_name:
                self.current_profile_name = profile_name
                
            # Genel ayarlar bölümü
            if 'Settings' not in config:
                config['Settings'] = {}
                
            # Son kullanılan profil adını kaydet
            config['Settings']['last_profile'] = self.current_profile_name
            
            # Profil bölümü
            section_name = f"Profile_{self.current_profile_name}"
            if section_name not in config:
                config[section_name] = {}
                
            # Tıklama verilerini JSON formatına dönüştür
            click_data = [click_action_to_dict(action) for action in self.click_actions]
            config[section_name]['click_data'] = json.dumps(click_data)
            
            # Tekrar ayarını kaydet
            config[section_name]['repeat'] = str(int(self.repeat_playback))
            
            # Gecikme kullanım ayarını kaydet
            config[section_name]['use_delays'] = str(int(self.use_recorded_delays))
            
            # Dosyaya kaydet
            with open(CONFIG_FILE, 'w') as configfile:
                config.write(configfile)
                
            print(f"Ayarlar '{CONFIG_FILE}' dosyasına kaydedildi. Profil: {self.current_profile_name}")
            return True
            
        except Exception as e:
            print(f"Ayarlar kaydedilirken hata oluştu: {e}")
            show_auto_close_warning(self, "Hata", f"Ayarlar kaydedilemedi: {e}")
            return False
    
    def load_settings(self, profile_name=None):
        """
        INI dosyasından tıklama verilerini ve ayarları yükler
        """
        try:
            if not os.path.exists(CONFIG_FILE):
                print(f"'{CONFIG_FILE}' dosyası bulunamadı.")
                return False
                
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE)
            
            # Profil adını belirle
            if profile_name is None:
                # Eğer profil adı belirtilmemişse, son kullanılan profili kullan
                if 'Settings' in config and 'last_profile' in config['Settings']:
                    profile_name = config['Settings']['last_profile']
                else:
                    profile_name = "default"
            
            # Profil bölümünü kontrol et
            section_name = f"Profile_{profile_name}"
            if section_name not in config:
                print(f"'{profile_name}' profili bulunamadı.")
                return False
                
            # Profil adını ayarla
            self.current_profile_name = profile_name
            
            # Tıklama verilerini yükle
            if 'click_data' in config[section_name]:
                click_data = json.loads(config[section_name]['click_data'])
                
                # Önceki tıklama verilerini temizle
                self.click_actions = []
                
                # Tıklama verilerini nesnelere dönüştür
                for data in click_data:
                    self.click_actions.append(dict_to_click_action(data))
                
                # Liste görünümünü güncelle
                self.update_click_list()
                self.update_status()
            
            # Tekrar ayarını yükle
            if 'repeat' in config[section_name]:
                self.repeat_playback = bool(int(config[section_name]['repeat']))
                self.repeat_checkbox.setChecked(self.repeat_playback)
            
            # Gecikme kullanım ayarını yükle
            if 'use_delays' in config[section_name]:
                self.use_recorded_delays = bool(int(config[section_name]['use_delays']))
                self.use_delays_checkbox.setChecked(self.use_recorded_delays)
                
            print(f"'{profile_name}' profili başarıyla yüklendi.")
            
            # Kullanıcıya bildir
            tiklama_sayisi = len(self.click_actions)
            if tiklama_sayisi > 0:
                self.status_label.setText(f"'{profile_name}' profili yüklendi - {tiklama_sayisi} tıklama")
                show_auto_close_info(self, "Profil Yüklendi", 
                                  f"'{profile_name}' profili başarıyla yüklendi.\n\n"
                                  f"Toplam {tiklama_sayisi} tıklama yüklendi.")
            else:
                self.status_label.setText(f"'{profile_name}' profili yüklendi (boş)")
                
            return True
            
        except Exception as e:
            print(f"Ayarlar yüklenirken hata oluştu: {e}")
            show_auto_close_warning(self, "Hata", f"Ayarlar yüklenemedi: {e}")
            return False

    def save_profile(self):
        """
        Tıklama verilerini ve ayarları bir profile kaydeder
        """
        profile_name = self.profile_name_input.text().strip()
        
        # Profil adını kontrol et
        if not profile_name:
            show_auto_close_warning(self, "Uyarı", "Lütfen geçerli bir profil adı girin.")
            return
            
        # Veri kontrolü
        if not self.click_actions:
            result = QMessageBox.question(self, "Boş Profil", 
                                         "Hiç tıklama kaydedilmemiş. Boş profil kaydetmek istiyor musunuz?",
                                         QMessageBox.Yes | QMessageBox.No)
            if result == QMessageBox.No:
                return
        
        # Ayarları kaydet
        if self.save_settings(profile_name):
            # Profil etiketini güncelle
            self.current_profile_name = profile_name
            self.profile_label.setText(f"Aktif Profil: {self.current_profile_name}")
            
            # Kullanıcıya bildir
            self.status_label.setText(f"'{profile_name}' profili kaydedildi")
            show_auto_close_info(self, "Kayıt Başarılı", 
                              f"'{profile_name}' profili başarıyla kaydedildi.\n\n"
                              f"Toplam {len(self.click_actions)} tıklama kaydedildi.")
    
    def load_profile(self):
        """
        Kullanıcının seçtiği profilden tıklama verilerini ve ayarları yükler.
        
        Kullanıcıdan profil adını alır, ilgili profilin varlığını kontrol eder
        ve varsa tıklama verilerini ve ayarları yükler. Profil yoksa veya başka bir
        hata oluşursa kullanıcıya bildirim gösterir.
        """
        profile_name = self.profile_name_input.text().strip()
        
        # Profil adını kontrol et
        if not profile_name:
            show_auto_close_warning(self, "Uyarı", "Lütfen geçerli bir profil adı girin.")
            return
            
        # Profilin varlığını kontrol et
        config = configparser.ConfigParser()
        
        if not os.path.exists(CONFIG_FILE):
            show_auto_close_warning(self, "Hata", f"'{CONFIG_FILE}' dosyası bulunamadı.")
            return
            
        config.read(CONFIG_FILE)
        section_name = f"Profile_{profile_name}"
        
        if section_name not in config:
            show_auto_close_warning(self, "Hata", f"'{profile_name}' profili bulunamadı.")
            return
            
        # Veri kaydedilmişse devam et
        self.load_settings(profile_name)
        
# Ana programın başlangıç noktası
if __name__ == "__main__":
    """
    Ana program başlangıç noktası.
    
    PyQt uygulamasını başlatır ve ana pencereyi gösterir.
    Uygulamanın giriş noktasıdır.
    """
    # Uygulama nesnesi oluştur
    app = QApplication(sys.argv)
    
    # Ana pencereyi oluştur
    window = PointRecorderApp()
    
    # Pencereyi göster
    window.show()
    
    # Uygulama döngüsünü başlat ve sonlandırma kodunu döndür
    sys.exit(app.exec_()) 