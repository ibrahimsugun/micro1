"""
# Geliştirilmiş Auto Heal + Buff Sistemi - Kullanıcı Arayüzü Modülü

Bu modül, Knight Online oyunu için geliştirilmiş otomatik iyileştirme ve buff sisteminin
kullanıcı arayüzü bileşenlerini içerir.

Özellikleri:
- 8 HP barı satırı için koordinat alma ve gösterme işlemleri
- Buff takibi için sayaç ve göstergeler
- Dinamik durum bildirimleri

Author: Claude AI
Version: 2.0
"""

import sys
import os
import json
import time
import threading
import keyboard
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QListWidget, QListWidgetItem, QLineEdit, 
    QMessageBox, QSpinBox, QCheckBox, QStatusBar, QGroupBox, QFormLayout,
    QProgressBar, QInputDialog, QFrame, QDialog, QDialogButtonBox,
    QScrollArea, QSizePolicy, QComboBox, QSlider
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize
from PyQt5.QtGui import QIcon, QFont, QColor
from pynput.mouse import Controller as MouseController
from pynput.keyboard import Listener as KeyboardListener

# AutoHealBuffWidget, HealRowWidget ve BuffWidget sınıflarını ekleyelim
class HealRowWidget(QWidget):
    """
    Auto Heal sisteminde kullanılan her bir HP satırı için widget.
    Sadece koordinat alma ve aktif/pasif durumu için gerekli alanları içerir.
    """
    def __init__(self, parent=None, row_index=0):
        super().__init__(parent)
        self.parent = parent
        self.row_index = row_index
        self.coords = []  # [x1, y1, x2, y2] - HP barının başlangıç ve bitiş koordinatları
        self.active = False
        self.setup_ui()
        
    def setup_ui(self):
        """UI bileşenlerini oluşturur"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Aktif/Pasif checkboxı
        self.active_checkbox = QCheckBox(f"Satır {self.row_index + 1}")
        self.active_checkbox.setChecked(False)
        self.active_checkbox.stateChanged.connect(self.on_active_changed)
        self.active_checkbox.setToolTip(f"Satır {self.row_index + 1} izlemeyi aktifleştirir/devre dışı bırakır")
        
        # Koordinat bilgisi
        self.coord_label = QLabel("Tanımlanmadı")
        self.coord_label.setToolTip("HP barının başlangıç ve bitiş koordinatları")
        
        # Koordinat alma butonu
        self.button = QPushButton("Koordinat Al")
        self.button.setFixedWidth(100)
        self.button.setToolTip("HP barının SOL ve SAĞ koordinatlarını almak için tıklayın")
        
        # Bileşenleri yerleştir
        layout.addWidget(self.active_checkbox)
        layout.addWidget(self.coord_label)
        layout.addWidget(self.button)
    
    def on_active_changed(self, state):
        """Aktif/Pasif durumu değiştiğinde çağrılır"""
        self.active = (state == Qt.Checked)
        
        # Durumu konsola logla
        print(f"Satır {self.row_index + 1} {'aktif' if self.active else 'pasif'} olarak ayarlandı")
    
    def set_coordinates(self, coords):
        """Koordinatları günceller ve gösterir"""
        self.coords = coords
        if len(coords) == 4:
            self.coord_label.setText(f"({coords[0]},{coords[1]}) - ({coords[2]},{coords[3]})")
        else:
            self.coord_label.setText(f"Koordinat 1: ({coords[0]},{coords[1]})")
        
        # Koordinatları konsola logla
        if len(coords) == 4:
            print(f"Satır {self.row_index + 1} için koordinatlar ayarlandı: ({coords[0]},{coords[1]}) - ({coords[2]},{coords[3]})")
        else:
            print(f"Satır {self.row_index + 1} için ilk koordinat ayarlandı: ({coords[0]},{coords[1]})")

class BuffWidget(QWidget):
    """
    Auto Buff sisteminde kullanılan her bir buff için widget.
    Zamanlayıcı bazlı çalışır, ekran kontrolü yapmaz.
    """
    def __init__(self, parent=None, buff_index=0, buff_name="Buff"):
        super().__init__(parent)
        self.parent = parent
        self.buff_index = buff_index
        self.buff_name = buff_name
        self.active = False
        self.key = ""
        self.duration = 60  # saniye
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timer)
        self.remaining_time = 0
        self.setup_ui()
    
    def setup_ui(self):
        """UI bileşenlerini oluşturur"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Aktif/Pasif checkboxı
        self.active_checkbox = QCheckBox(f"{self.buff_name}")
        self.active_checkbox.setChecked(False)
        self.active_checkbox.stateChanged.connect(self.on_active_changed)
        self.active_checkbox.setToolTip(f"{self.buff_name} kullanımını aktifleştirir/devre dışı bırakır")
        
        # Tuş seçimi
        self.key_label = QLabel("Tuş:")
        self.key_combo = QComboBox()
        # F1-F12 tuşlarını ekle
        self.key_combo.addItem("Seç")
        for i in range(1, 13):
            self.key_combo.addItem(f"F{i}")
        # 0-9 tuşlarını ekle
        for i in range(10):
            self.key_combo.addItem(str(i))
        self.key_combo.currentTextChanged.connect(self.on_key_changed)
        self.key_combo.setToolTip(f"{self.buff_name} için kullanılacak tuşu seçin")
        
        # Süre seçimi
        self.duration_label = QLabel("Süre (sn):")
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 3600)  # 1 saniye - 1 saat
        self.duration_spin.setValue(60)
        self.duration_spin.valueChanged.connect(self.on_duration_changed)
        self.duration_spin.setToolTip(f"{self.buff_name} kullanım süresi (saniye)")
        
        # İlerleme çubuğu
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self.duration)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v / %m sn")
        self.progress_bar.setToolTip(f"{self.buff_name} için kalan süre")
        
        # Bileşenleri yerleştir
        layout.addWidget(self.active_checkbox)
        layout.addWidget(self.key_label)
        layout.addWidget(self.key_combo)
        layout.addWidget(self.duration_label)
        layout.addWidget(self.duration_spin)
        layout.addWidget(self.progress_bar, 1)  # 1: stretch faktörü
    
    def on_active_changed(self, state):
        """Aktif/Pasif durumu değiştiğinde çağrılır"""
        self.active = (state == Qt.Checked)
        
        # Konsola logla
        print(f"{self.buff_name} {'aktif' if self.active else 'pasif'} olarak ayarlandı")
    
    def on_key_changed(self, text):
        """Tuş değiştiğinde çağrılır"""
        if text != "Seç":
            self.key = text
            # Konsola logla
            print(f"{self.buff_name} tuşu '{text}' olarak ayarlandı")
        else:
            self.key = ""
    
    def on_duration_changed(self, value):
        """Süre değiştiğinde çağrılır"""
        self.duration = value
        self.progress_bar.setRange(0, value)
        self.progress_bar.setFormat(f"%v / {value} sn")
        
        # Konsola logla
        print(f"{self.buff_name} süresi {value} saniye olarak ayarlandı")
    
    def update_timer(self):
        """Zamanlayıcıyı günceller"""
        if self.remaining_time > 0:
            self.remaining_time -= 1
            self.progress_bar.setValue(self.remaining_time)
        else:
            # Süre doldu, timerı durdur
            self.timer.stop()
            # Süreyi yeniden ayarla
            self.remaining_time = self.duration
            self.progress_bar.setValue(self.remaining_time)
            # Timer'ı yeniden başlat
            self.timer.start(1000)  # 1 saniye aralıklarla
            
            # Konsola logla
            print(f"{self.buff_name} süresi doldu, yeniden başlatılıyor")
    
    def start_timer(self):
        """Zamanlayıcıyı başlatır"""
        if self.active and self.key:
            self.remaining_time = self.duration
            self.progress_bar.setValue(self.remaining_time)
            self.timer.start(1000)  # 1 saniye aralıklarla
            # Konsola logla
            print(f"{self.buff_name} zamanlayıcısı başlatıldı. Süre: {self.duration} saniye")
            return True
        else:
            # Konsola logla
            if not self.active:
                print(f"{self.buff_name} aktif olmadığı için zamanlayıcı başlatılmadı")
            elif not self.key:
                print(f"{self.buff_name} için tuş tanımlanmadığı için zamanlayıcı başlatılmadı")
            return False
    
    def stop_timer(self):
        """Zamanlayıcıyı durdurur"""
        if self.timer.isActive():
            self.timer.stop()
            # Konsola logla
            print(f"{self.buff_name} zamanlayıcısı durduruldu")
            return True
        return False
    
    def get_key(self):
        """Buff için kullanılacak tuşu döndürür"""
        return self.key
    
    def get_duration(self):
        """Buff süresi döndürür"""
        return self.duration

class AutoHealBuffWidget(QWidget):
    """
    Auto Heal ve Buff sistemini içeren ana widget.
    - Tüm satırlar için ortak heal tuşu kullanır
    - Buff ve AC için zamanlayıcı bazlı çalışır
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        
        # Statusbar referansını al
        self.statusbar = None
        if hasattr(parent, 'statusbar'):
            self.statusbar = parent.statusbar
        
        # Satır ve buff listeleri
        self.heal_rows = []
        self.buff_widgets = []
        
        # HP yüzdesi ve heal tuşları
        self.heal_percentage = 80
        self.heal_key = "1"
        self.heal_active = False
        
        # Toplu heal ayarları
        self.mass_heal_percentage = 60
        self.mass_heal_key = "2"
        self.mass_heal_active = False
        self.party_check_enabled = False
        
        # Kontrol frekansı ayarları (milisaniye)
        self.heal_check_interval = 500  # 500ms varsayılan değer
        self.buff_check_interval = 500  # 500ms varsayılan değer
        
        # Çalışma durumu
        self.working = False
        
        # UI oluştur
        self.setup_ui()
        
    def load_config(self, config_section):
        """
        Konfigürasyon bölümünden ayarları yükler
        
        :param config_section: ConfigParser bölümü
        """
        try:
            # HP yüzdesi
            if 'heal_percentage' in config_section:
                self.heal_percentage = int(config_section['heal_percentage'])
                if hasattr(self, 'hp_percentage_spin'):
                    self.hp_percentage_spin.setValue(self.heal_percentage)
            
            # Heal tuşu
            if 'heal_key' in config_section:
                self.heal_key = config_section['heal_key']
                if hasattr(self, 'heal_key_combo') and self.heal_key_combo.findText(self.heal_key) != -1:
                    self.heal_key_combo.setCurrentText(self.heal_key)
            
            # Heal aktif durumu
            if 'heal_active' in config_section:
                self.heal_active = config_section.getboolean('heal_active')
                if hasattr(self, 'heal_active_checkbox'):
                    self.heal_active_checkbox.setChecked(self.heal_active)
                    self.on_heal_active_changed(Qt.Checked if self.heal_active else Qt.Unchecked)
            
            # Toplu heal yüzdesi
            if 'mass_heal_percentage' in config_section:
                self.mass_heal_percentage = int(config_section['mass_heal_percentage'])
                if hasattr(self, 'mass_heal_percentage_spin'):
                    self.mass_heal_percentage_spin.setValue(self.mass_heal_percentage)
            
            # Toplu heal tuşu
            if 'mass_heal_key' in config_section:
                self.mass_heal_key = config_section['mass_heal_key']
                if hasattr(self, 'mass_heal_key_combo') and self.mass_heal_key_combo.findText(self.mass_heal_key) != -1:
                    self.mass_heal_key_combo.setCurrentText(self.mass_heal_key)
            
            # Toplu heal aktif durumu
            if 'mass_heal_active' in config_section:
                self.mass_heal_active = config_section.getboolean('mass_heal_active')
                if hasattr(self, 'mass_heal_active_checkbox'):
                    self.mass_heal_active_checkbox.setChecked(self.mass_heal_active)
                    self.on_mass_heal_active_changed(Qt.Checked if self.mass_heal_active else Qt.Unchecked)
            
            # Parti kontrolü
            if 'party_check_enabled' in config_section:
                self.party_check_enabled = config_section.getboolean('party_check_enabled')
                if hasattr(self, 'mass_heal_party_check'):
                    self.mass_heal_party_check.setChecked(self.party_check_enabled)
            
            # Kontrol aralıkları
            if 'heal_check_interval' in config_section:
                self.heal_check_interval = int(config_section['heal_check_interval'])
                if hasattr(self, 'heal_freq_slider'):
                    self.heal_freq_slider.setValue(self.heal_check_interval)
            
            if 'buff_check_interval' in config_section:
                self.buff_check_interval = int(config_section['buff_check_interval'])
                if hasattr(self, 'buff_freq_slider'):
                    self.buff_freq_slider.setValue(self.buff_check_interval)
            
            # Satır ayarları
            for i in range(8):
                row_key = f'row_{i}_active'
                if row_key in config_section and i < len(self.heal_rows):
                    active = config_section.getboolean(row_key)
                    self.heal_rows[i].active_checkbox.setChecked(active)
                    self.heal_rows[i].active = active
                
                row_coords = f'row_{i}_coords'
                if row_coords in config_section and i < len(self.heal_rows):
                    try:
                        coords = eval(config_section[row_coords])
                        if isinstance(coords, list) and len(coords) == 4:
                            self.heal_rows[i].set_coordinates(coords)
                    except:
                        pass
            
            # Log mesajı
            print("Ayarlar başarıyla yüklendi.")
            if self.statusbar:
                self.statusbar.showMessage("Ayarlar başarıyla yüklendi.", 3000)
                
        except Exception as e:
            print(f"Ayarlar yüklenirken hata: {str(e)}")
            if self.statusbar:
                self.statusbar.showMessage(f"Ayarlar yüklenirken hata: {str(e)}", 3000)
                
    def save_config(self, config_section):
        """
        Konfigürasyon bölümüne ayarları kaydeder
        
        :param config_section: ConfigParser bölümü
        :return: Güncellenen config_section
        """
        try:
            # HP yüzdesi
            config_section['heal_percentage'] = str(self.heal_percentage)
            
            # Heal tuşu ve aktiflik
            config_section['heal_key'] = self.heal_key
            config_section['heal_active'] = str(self.heal_active)
            
            # Toplu heal yüzdesi, tuşu ve aktiflik
            config_section['mass_heal_percentage'] = str(self.mass_heal_percentage)
            config_section['mass_heal_key'] = self.mass_heal_key
            config_section['mass_heal_active'] = str(self.mass_heal_active)
            
            # Parti kontrolü
            config_section['party_check_enabled'] = str(self.party_check_enabled)
            
            # Kontrol aralıkları
            config_section['heal_check_interval'] = str(self.heal_check_interval)
            config_section['buff_check_interval'] = str(self.buff_check_interval)
            
            # Satır ayarları
            for i, row in enumerate(self.heal_rows):
                config_section[f'row_{i}_active'] = str(row.active)
                config_section[f'row_{i}_coords'] = str(row.coords)
            
            # Buff widget ayarları
            for i, buff in enumerate(self.buff_widgets):
                config_section[f'buff_{i}_active'] = str(buff.active)
                config_section[f'buff_{i}_key'] = buff.key
                config_section[f'buff_{i}_duration'] = str(buff.duration)
                config_section[f'buff_{i}_name'] = buff.buff_name
            
            # Log mesajı
            print("Ayarlar başarıyla kaydedildi.")
            if self.statusbar:
                self.statusbar.showMessage("Ayarlar başarıyla kaydedildi.", 3000)
            
            return config_section
        except Exception as e:
            print(f"Ayarlar kaydedilirken hata: {str(e)}")
            if self.statusbar:
                self.statusbar.showMessage(f"Ayarlar kaydedilirken hata: {str(e)}", 3000)
            return config_section
    
    def setup_ui(self):
        """
        UI bileşenlerini oluşturur.
        - Heal satırları
        - Heal ayarları bölümü
        - Buff bölümü
        - Kontrol aralığı ayarları
        """
        # Ana layout
        main_layout = QVBoxLayout(self)
        
        # Scroll Area oluştur
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll.setWidget(scroll_widget)
        
        # HealRowWidget satırları oluştur
        heal_rows_group = QGroupBox("HP Bar Satırları")
        heal_rows_layout = QVBoxLayout(heal_rows_group)
        
        for i in range(8):
            row_widget = HealRowWidget(self, i)
            self.heal_rows.append(row_widget)
            heal_rows_layout.addWidget(row_widget)
        
        scroll_layout.addWidget(heal_rows_group)
        
        # Ana ayarlar grup kutusu
        settings_group = QGroupBox("İyileştirme Ayarları")
        settings_layout = QVBoxLayout(settings_group)
        
        # İyileştirme bölümü
        heal_layout = QHBoxLayout()
        
        # Heal aktiflik kontrolü
        self.heal_active_checkbox = QCheckBox("İyileştirme Aktif")
        self.heal_active_checkbox.setChecked(self.heal_active)
        self.heal_active_checkbox.stateChanged.connect(self.on_heal_active_changed)
        self.heal_active_checkbox.setToolTip("İyileştirme sistemini aktifleştirir/devre dışı bırakır")
        heal_layout.addWidget(self.heal_active_checkbox)
        
        # Heal tuşu seçimi
        heal_key_layout = QHBoxLayout()
        heal_key_layout.addWidget(QLabel("İyileştirme Tuşu:"))
        self.heal_key_combo = QComboBox()
        # F1-F12 tuşlarını ekle
        for i in range(1, 13):
            self.heal_key_combo.addItem(f"F{i}")
        # 0-9 tuşlarını ekle
        for i in range(10):
            self.heal_key_combo.addItem(str(i))
        self.heal_key_combo.setCurrentText(self.heal_key)
        self.heal_key_combo.currentTextChanged.connect(self.on_heal_key_changed)
        self.heal_key_combo.setToolTip("İyileştirme için kullanılacak tuş")
        heal_key_layout.addWidget(self.heal_key_combo)
        heal_layout.addLayout(heal_key_layout)
        
        # HP Yüzdesi
        hp_percentage_layout = QHBoxLayout()
        hp_percentage_layout.addWidget(QLabel("HP Yüzdesi:"))
        self.hp_percentage_spin = QSpinBox()
        self.hp_percentage_spin.setRange(1, 99)
        self.hp_percentage_spin.setValue(self.heal_percentage)
        self.hp_percentage_spin.setSuffix("%")
        self.hp_percentage_spin.valueChanged.connect(self.on_hp_percentage_changed)
        self.hp_percentage_spin.setToolTip("HP bu yüzdenin altına düştüğünde iyileştirme yapılır")
        hp_percentage_layout.addWidget(self.hp_percentage_spin)
        heal_layout.addLayout(hp_percentage_layout)
        
        settings_layout.addLayout(heal_layout)
        
        # Toplu İyileştirme bölümü
        mass_heal_group = QGroupBox("Toplu İyileştirme")
        mass_heal_layout = QVBoxLayout(mass_heal_group)
        
        # Toplu heal aktiflik kontrolü
        mass_heal_control_layout = QHBoxLayout()
        self.mass_heal_active_checkbox = QCheckBox("Toplu İyileştirme Aktif")
        self.mass_heal_active_checkbox.setChecked(self.mass_heal_active)
        self.mass_heal_active_checkbox.stateChanged.connect(self.on_mass_heal_active_changed)
        self.mass_heal_active_checkbox.setToolTip("Toplu iyileştirme sistemini aktifleştirir/devre dışı bırakır")
        mass_heal_control_layout.addWidget(self.mass_heal_active_checkbox)
        
        # Parti kontrolü
        self.mass_heal_party_check = QCheckBox("Parti Seçim Kontrolü")
        self.mass_heal_party_check.setChecked(self.party_check_enabled)
        self.mass_heal_party_check.stateChanged.connect(self.on_mass_heal_party_check_changed)
        self.mass_heal_party_check.setToolTip("İşaretlenirse, tüm partiye iyileştirme yapılır")
        mass_heal_control_layout.addWidget(self.mass_heal_party_check)
        
        mass_heal_layout.addLayout(mass_heal_control_layout)
        
        # Toplu heal ayarları
        mass_heal_settings_layout = QHBoxLayout()
        
        # Toplu heal tuşu
        mass_heal_key_layout = QHBoxLayout()
        mass_heal_key_layout.addWidget(QLabel("Tuş:"))
        self.mass_heal_key_combo = QComboBox()
        # F1-F12 tuşlarını ekle
        for i in range(1, 13):
            self.mass_heal_key_combo.addItem(f"F{i}")
        # 0-9 tuşlarını ekle
        for i in range(10):
            self.mass_heal_key_combo.addItem(str(i))
        self.mass_heal_key_combo.setCurrentText(self.mass_heal_key)
        self.mass_heal_key_combo.currentTextChanged.connect(self.on_mass_heal_key_changed)
        self.mass_heal_key_combo.setToolTip("Toplu iyileştirme için kullanılacak tuş")
        mass_heal_key_layout.addWidget(self.mass_heal_key_combo)
        mass_heal_settings_layout.addLayout(mass_heal_key_layout)
        
        # Toplu heal yüzdesi
        mass_heal_percentage_layout = QHBoxLayout()
        mass_heal_percentage_layout.addWidget(QLabel("HP Yüzdesi:"))
        self.mass_heal_percentage_spin = QSpinBox()
        self.mass_heal_percentage_spin.setRange(1, 99)
        self.mass_heal_percentage_spin.setValue(self.mass_heal_percentage)
        self.mass_heal_percentage_spin.setSuffix("%")
        self.mass_heal_percentage_spin.valueChanged.connect(self.on_mass_heal_percentage_changed)
        self.mass_heal_percentage_spin.setToolTip("HP bu yüzdenin altına düştüğünde toplu iyileştirme yapılır")
        mass_heal_percentage_layout.addWidget(self.mass_heal_percentage_spin)
        mass_heal_settings_layout.addLayout(mass_heal_percentage_layout)
        
        mass_heal_layout.addLayout(mass_heal_settings_layout)
        settings_layout.addWidget(mass_heal_group)
        
        # Kontrol frekansı ayarları
        freq_group = QGroupBox("Kontrol Frekansı")
        freq_layout = QVBoxLayout(freq_group)
        
        # Heal kontrol frekansı
        heal_freq_layout = QHBoxLayout()
        heal_freq_layout.addWidget(QLabel("İyileştirme Kontrolü (ms):"))
        self.heal_freq_slider = QSlider(Qt.Horizontal)
        self.heal_freq_slider.setRange(300, 900)
        self.heal_freq_slider.setSingleStep(100)
        self.heal_freq_slider.setPageStep(100)
        self.heal_freq_slider.setTickInterval(100)
        self.heal_freq_slider.setTickPosition(QSlider.TicksBelow)
        self.heal_freq_slider.setValue(self.heal_check_interval)
        self.heal_freq_slider.valueChanged.connect(self.on_heal_freq_changed)
        self.heal_freq_slider.setToolTip("İyileştirme için ekran kontrol frekansı (milisaniye)")
        heal_freq_layout.addWidget(self.heal_freq_slider)
        self.heal_freq_label = QLabel(f"{self.heal_check_interval} ms")
        heal_freq_layout.addWidget(self.heal_freq_label)
        freq_layout.addLayout(heal_freq_layout)
        
        # Buff kontrol frekansı
        buff_freq_layout = QHBoxLayout()
        buff_freq_layout.addWidget(QLabel("Buff Kontrolü (ms):"))
        self.buff_freq_slider = QSlider(Qt.Horizontal)
        self.buff_freq_slider.setRange(300, 900)
        self.buff_freq_slider.setSingleStep(100)
        self.buff_freq_slider.setPageStep(100)
        self.buff_freq_slider.setTickInterval(100)
        self.buff_freq_slider.setTickPosition(QSlider.TicksBelow)
        self.buff_freq_slider.setValue(self.buff_check_interval)
        self.buff_freq_slider.valueChanged.connect(self.on_buff_freq_changed)
        self.buff_freq_slider.setToolTip("Buff zamanlayıcısı için kontrol frekansı (milisaniye)")
        buff_freq_layout.addWidget(self.buff_freq_slider)
        self.buff_freq_label = QLabel(f"{self.buff_check_interval} ms")
        buff_freq_layout.addWidget(self.buff_freq_label)
        freq_layout.addLayout(buff_freq_layout)
        
        settings_layout.addWidget(freq_group)
        scroll_layout.addWidget(settings_group)
        
        # Buff widget'ları bölümü
        buff_group = QGroupBox("Buff Yönetimi")
        buff_layout = QVBoxLayout(buff_group)
        
        # Buff widget'ları oluştur (Normal Buff ve AC)
        buff_widget = BuffWidget(self, 0, "Normal Buff")
        ac_widget = BuffWidget(self, 1, "AC (Anti-Cheat)")
        
        self.buff_widgets.append(buff_widget)
        self.buff_widgets.append(ac_widget)
        
        buff_layout.addWidget(buff_widget)
        buff_layout.addWidget(ac_widget)
        
        scroll_layout.addWidget(buff_group)
        
        # Ana layout'a scroll area ekle
        main_layout.addWidget(scroll)
        
        # Arayüzü logla
        print("Auto Heal ve Buff arayüzü oluşturuldu.")
        if self.statusbar:
            self.statusbar.showMessage("Hazır", 3000)
    
    def on_heal_active_changed(self, state):
        """Heal aktifliği değiştiğinde çağrılır"""
        self.heal_active = (state == Qt.Checked)
        print(f"İyileştirme aktif durumu değişti: {self.heal_active}")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"İyileştirme {'aktif' if self.heal_active else 'pasif'} duruma getirildi", 3000)
    
    def on_heal_key_changed(self, text):
        """Heal tuşu değiştiğinde çağrılır"""
        self.heal_key = text
        print(f"İyileştirme tuşu '{text}' olarak ayarlandı")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"İyileştirme tuşu '{text}' olarak ayarlandı", 3000)
    
    def on_mass_heal_active_changed(self, state):
        """Toplu Heal aktifliği değiştiğinde çağrılır"""
        self.mass_heal_active = (state == Qt.Checked)
        print(f"Toplu iyileştirme aktif durumu değişti: {self.mass_heal_active}")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"Toplu iyileştirme {'aktif' if self.mass_heal_active else 'pasif'} duruma getirildi", 3000)
    
    def on_mass_heal_key_changed(self, text):
        """Toplu heal tuşu değiştiğinde çağrılır"""
        self.mass_heal_key = text
        print(f"Toplu iyileştirme tuşu '{text}' olarak ayarlandı")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"Toplu iyileştirme tuşu '{text}' olarak ayarlandı", 3000)
    
    def on_mass_heal_percentage_changed(self, value):
        """Toplu heal yüzdesi değiştiğinde çağrılır"""
        self.mass_heal_percentage = value
        print(f"Toplu iyileştirme yüzdesi %{value} olarak ayarlandı")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"Toplu iyileştirme yüzdesi %{value} olarak ayarlandı", 3000)
    
    def on_mass_heal_party_check_changed(self, state):
        """Toplu heal parti kontrolü değiştiğinde çağrılır"""
        self.party_check_enabled = (state == Qt.Checked)
        print(f"Parti kontrolü {'aktif' if self.party_check_enabled else 'pasif'} olarak ayarlandı")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"Parti kontrolü {'aktif' if self.party_check_enabled else 'pasif'} olarak ayarlandı", 3000)
    
    def on_hp_percentage_changed(self, value):
        """HP yüzdesi değiştiğinde çağrılır"""
        self.heal_percentage = value
        print(f"İyileştirme yüzdesi %{value} olarak ayarlandı")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"İyileştirme yüzdesi %{value} olarak ayarlandı", 3000)
    
    def on_heal_freq_changed(self, value):
        """Heal kontrol frekansı değiştiğinde çağrılır"""
        # Değeri 100'e yuvarla
        value = (value // 100) * 100
        if value < 300:
            value = 300
        elif value > 900:
            value = 900
            
        self.heal_check_interval = value
        if hasattr(self, 'heal_freq_label'):
            self.heal_freq_label.setText(f"{value} ms")
        
        print(f"İyileştirme kontrol frekansı {value} ms olarak ayarlandı")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"İyileştirme kontrol frekansı {value} ms olarak ayarlandı", 3000)
    
    def on_buff_freq_changed(self, value):
        """Buff kontrol frekansı değiştiğinde çağrılır"""
        # Değeri 100'e yuvarla
        value = (value // 100) * 100
        if value < 300:
            value = 300
        elif value > 900:
            value = 900
            
        self.buff_check_interval = value
        if hasattr(self, 'buff_freq_label'):
            self.buff_freq_label.setText(f"{value} ms")
        
        print(f"Buff kontrol frekansı {value} ms olarak ayarlandı")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"Buff kontrol frekansı {value} ms olarak ayarlandı", 3000)
    
    def take_row_coordinates(self, row_index):
        """Satır için koordinat alma işlemini başlatır"""
        print(f"Satır {row_index + 1} için koordinat alma işlemi başlatıldı")
        # Bu metodu kullanarak koordinat alma işlemi başlatılır
        # Gerçek koordinat alma işlemi ana pencere tarafından yapılacak
    
    def set_row_coordinates(self, row_index, x, y):
        """Satır için koordinatları ayarlar"""
        if 0 <= row_index < len(self.heal_rows):
            row = self.heal_rows[row_index]
            
            # İlk nokta
            if len(row.coords) < 2:
                row.coords = [x, y]
                row.set_coordinates(row.coords)
                print(f"Satır {row_index + 1} için ilk koordinat ayarlandı: ({x}, {y})")
                
                # Statusbar mesajını göster
                if self.statusbar:
                    self.statusbar.showMessage(f"Satır {row_index + 1} için ilk koordinat ayarlandı. Şimdi ikinci koordinatı seçin.", 3000)
            # İkinci nokta
            else:
                row.coords.extend([x, y])
                row.set_coordinates(row.coords)
                print(f"Satır {row_index + 1} için ikinci koordinat ayarlandı: ({x}, {y})")
                
                # Statusbar mesajını göster
                if self.statusbar:
                    self.statusbar.showMessage(f"Satır {row_index + 1} için tüm koordinatlar ayarlandı.", 3000)

    def start_working(self):
        """
        Heal ve buff işlemi için gerekli değerleri toplayıp çalıştırır.
        
        Returns:
            (rows_data, heal_data, buffs_data) üçlüsü.
        """
        # Çalışma durumunu aktif yap
        self.working = True
        
        # HP satırlarından veri topla
        rows_data = []
        for row in self.heal_rows:
            row_data = {
                "active": row.active,
                "coords": row.coords,
                "click_coords": [],  # Fare ile tıklama seçeneği kaldırıldığı için boş bırakıyoruz
                "use_click": False   # Fare ile tıklama seçeneği kaldırıldığı için False
            }
            rows_data.append(row_data)
        
        # Heal ayarlarını topla
        heal_data = {
            "heal_active": self.heal_active,
            "heal_key": self.heal_key,
            "mass_heal_active": self.mass_heal_active,
            "mass_heal_key": self.mass_heal_key,
            "mass_heal_percentage": self.mass_heal_percentage,
            "mass_heal_party_check": self.party_check_enabled
        }
        
        # Buff ayarlarını topla
        buffs_data = {}
        for i, buff_widget in enumerate(self.buff_widgets):
            buffs_data[str(i)] = {
                "name": buff_widget.buff_name,
                "key": buff_widget.get_key(),
                "active": buff_widget.active,
                "duration": buff_widget.get_duration()
            }
            
            # Buff zamanlayıcısını başlat
            if buff_widget.active:
                buff_widget.start_timer()
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage("Otomatik iyileştirme ve buff sistemi çalışıyor...", 5000)
        
        print("AutoHealBuffWidget çalışma durumu: Aktif")
        
        return rows_data, heal_data, buffs_data
    
    def stop_working(self):
        """
        Çalışma durumunu durdurur ve tüm buff zamanlayıcılarını durdurur.
        """
        # Çalışma durumunu güncelle
        self.working = False
        
        # Buff zamanlayıcılarını durdur
        for buff_widget in self.buff_widgets:
            buff_widget.stop_timer()
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage("Otomatik iyileştirme ve buff sistemi durduruldu.", 5000)
            
        print("AutoHealBuffWidget çalışma durumu: Durduruldu")

# Sinyaller için sınıf oluşturalım
class UpdateSignals(QObject):
    update_progress = pyqtSignal(str)

class AutoHealUI(QMainWindow):
    """
    Knight Online otomatik iyileştirme ve buff sistemi ana penceresi
    """
    def __init__(self):
        super().__init__()
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        
        # Ana düzen ve widget oluşturma
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # AutoHealBuffWidget'ı ekle
        self.auto_heal_buff_widget = AutoHealBuffWidget(self)
        self.main_layout.addWidget(self.auto_heal_buff_widget)
        
        # Buff yönetimi bileşenlerini oluştur
        self.buffs_layout = QVBoxLayout()
        self.main_layout.addLayout(self.buffs_layout)
        self._create_buff_management()
        
        # Kaydet/Yükle düğmelerini oluştur
        self._create_save_load_buttons()
        
        # Başlat/Durdur düğmelerini oluştur
        self._create_start_stop_buttons()
        
        # UI'ı başlat
        self.init_ui()
        
    def init_ui(self):
        """Kullanıcı arayüzünü başlatır"""
        self.setWindowTitle("AutoHeal & Buff Sistemi")
        self.setGeometry(100, 100, 800, 600)
        
        # UI'ı özelleştir
        self._setup_ui()
        
        # Başlangıçta buffları yükle (eğer dosya varsa)
        self.load_buffs()
        
        # Pencereyi göster
        self.show()
        print("AutoHeal UI başlatıldı")
    
    def _setup_ui(self):
        """
        Kullanıcı arayüzü bileşenlerini oluşturur.
        """
        try:
            # Ana pencere ayarları
            self.setWindowTitle("AutoHeal Bufflar")
            self.setGeometry(100, 100, 600, 500)
            
            # Ana widget ve layout
            main_widget = QWidget()
            main_layout = QVBoxLayout()
            main_widget.setLayout(main_layout)
            self.setCentralWidget(main_widget)
            
            # Durum çubuğu
            self.statusbar.showMessage("Hazır", 3000)
            
            print("Ana UI oluşturuldu")
        except Exception as e:
            print(f"UI kurulum hatası: {e}")
    
    def _create_buff_management(self):
        """
        Buff yönetim panelini oluşturur.
        """
        try:
            # Buff Yönetim Paneli
            buff_group = QGroupBox("Buff Yönetimi")
            buff_layout = QVBoxLayout()
            
            # Buff Ekleme Kısmı
            add_layout = QHBoxLayout()
            self.buff_name_input = QLineEdit()
            self.buff_name_input.setPlaceholderText("Buff adı girin...")
            add_layout.addWidget(self.buff_name_input)
            
            add_btn = QPushButton("Ekle")
            add_btn.clicked.connect(self.add_buff_to_list)
            add_layout.addWidget(add_btn)
            buff_layout.addLayout(add_layout)
            
            # Buff Listesi
            self.buffs_list = QListWidget()
            self.buffs_list.setSpacing(5)
            buff_layout.addWidget(self.buffs_list)
            
            buff_group.setLayout(buff_layout)
            self.buffs_layout.addWidget(buff_group)
            
            print("Buff yönetim paneli oluşturuldu")
        except Exception as e:
            print(f"Buff yönetim paneli oluşturma hatası: {e}")
    
    def _create_save_load_buttons(self):
        """
        Ayarları kaydetme ve yükleme düğmelerini oluşturur.
        """
        try:
            # Kaydet/Yükle düğmeleri
            save_load_layout = QHBoxLayout()
            
            # Buff Ekle düğmesi
            add_buff_btn = QPushButton("Buff Ekle")
            add_buff_btn.clicked.connect(self.add_buff_to_list)
            save_load_layout.addWidget(add_buff_btn)
            
            # Ayarları Kaydet düğmesi
            save_btn = QPushButton("Buffları Kaydet")
            save_btn.clicked.connect(self.save_buffs)
            save_load_layout.addWidget(save_btn)
            
            # Ayarları Yükle düğmesi
            load_btn = QPushButton("Buffları Yükle")
            load_btn.clicked.connect(self.load_buffs)
            save_load_layout.addWidget(load_btn)
            
            self.buffs_layout.addLayout(save_load_layout)
            
            print("Kaydet/Yükle düğmeleri oluşturuldu")
        except Exception as e:
            print(f"Kaydet/Yükle düğmeleri oluşturma hatası: {e}")
    
    def _create_start_stop_buttons(self):
        """
        Başlatma ve durdurma düğmelerini oluşturur.
        """
        try:
            # Başlat/Durdur düğmeleri
            start_stop_layout = QHBoxLayout()
            
            # Başlat düğmesi
            self.start_btn = QPushButton("Başlat")
            self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
            self.start_btn.clicked.connect(self.start_auto_heal)
            start_stop_layout.addWidget(self.start_btn)
            
            # Durdur düğmesi
            self.stop_btn = QPushButton("Durdur")
            self.stop_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 10px;")
            self.stop_btn.clicked.connect(self.stop_auto_heal)
            self.stop_btn.setEnabled(False)
            start_stop_layout.addWidget(self.stop_btn)
            
            self.buffs_layout.addLayout(start_stop_layout)
            
            print("Başlat/Durdur düğmeleri oluşturuldu")
        except Exception as e:
            print(f"Başlat/Durdur düğmeleri oluşturma hatası: {e}")
            
    def start_auto_heal(self):
        """
        Auto Heal sistemini başlatır
        """
        print("Auto Heal başlatıldı")
        self.statusbar.showMessage("Auto Heal başlatıldı", 3000)
        
    def stop_auto_heal(self):
        """
        Auto Heal sistemini durdurur
        """
        print("Auto Heal durduruldu")
        self.statusbar.showMessage("Auto Heal durduruldu", 3000)

    def on_heal_active_changed(self, state):
        """Heal aktifliği değiştiğinde çağrılır"""
        self.heal_active = (state == Qt.Checked)
        print(f"İyileştirme aktif durumu değişti: {self.heal_active}")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"İyileştirme {'aktif' if self.heal_active else 'pasif'} duruma getirildi", 3000)
    
    def on_heal_key_changed(self, text):
        """Heal tuşu değiştiğinde çağrılır"""
        self.heal_key = text
        print(f"İyileştirme tuşu '{text}' olarak ayarlandı")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"İyileştirme tuşu '{text}' olarak ayarlandı", 3000)
    
    def on_mass_heal_active_changed(self, state):
        """Toplu Heal aktifliği değiştiğinde çağrılır"""
        self.mass_heal_active = (state == Qt.Checked)
        print(f"Toplu iyileştirme aktif durumu değişti: {self.mass_heal_active}")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"Toplu iyileştirme {'aktif' if self.mass_heal_active else 'pasif'} duruma getirildi", 3000)
    
    def on_mass_heal_key_changed(self, text):
        """Toplu heal tuşu değiştiğinde çağrılır"""
        self.mass_heal_key = text
        print(f"Toplu iyileştirme tuşu '{text}' olarak ayarlandı")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"Toplu iyileştirme tuşu '{text}' olarak ayarlandı", 3000)
    
    def on_mass_heal_percentage_changed(self, value):
        """Toplu heal yüzdesi değiştiğinde çağrılır"""
        self.mass_heal_percentage = value
        print(f"Toplu iyileştirme yüzdesi %{value} olarak ayarlandı")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"Toplu iyileştirme yüzdesi %{value} olarak ayarlandı", 3000)
    
    def on_mass_heal_party_check_changed(self, state):
        """Toplu heal parti kontrolü değiştiğinde çağrılır"""
        self.party_check_enabled = (state == Qt.Checked)
        print(f"Parti kontrolü {'aktif' if self.party_check_enabled else 'pasif'} olarak ayarlandı")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"Parti kontrolü {'aktif' if self.party_check_enabled else 'pasif'} olarak ayarlandı", 3000)
    
    def on_hp_percentage_changed(self, value):
        """HP yüzdesi değiştiğinde çağrılır"""
        self.heal_percentage = value
        print(f"İyileştirme yüzdesi %{value} olarak ayarlandı")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"İyileştirme yüzdesi %{value} olarak ayarlandı", 3000)
    
    def on_heal_freq_changed(self, value):
        """Heal kontrol frekansı değiştiğinde çağrılır"""
        # Değeri 100'e yuvarla
        value = (value // 100) * 100
        if value < 300:
            value = 300
        elif value > 900:
            value = 900
            
        self.heal_check_interval = value
        if hasattr(self, 'heal_freq_label'):
            self.heal_freq_label.setText(f"{value} ms")
        
        print(f"İyileştirme kontrol frekansı {value} ms olarak ayarlandı")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"İyileştirme kontrol frekansı {value} ms olarak ayarlandı", 3000)
    
    def on_buff_freq_changed(self, value):
        """Buff kontrol frekansı değiştiğinde çağrılır"""
        # Değeri 100'e yuvarla
        value = (value // 100) * 100
        if value < 300:
            value = 300
        elif value > 900:
            value = 900
            
        self.buff_check_interval = value
        if hasattr(self, 'buff_freq_label'):
            self.buff_freq_label.setText(f"{value} ms")
        
        print(f"Buff kontrol frekansı {value} ms olarak ayarlandı")
        
        # Statusbar mesajını göster
        if self.statusbar:
            self.statusbar.showMessage(f"Buff kontrol frekansı {value} ms olarak ayarlandı", 3000)
    
    def take_row_coordinates(self, row_index):
        """Satır için koordinat alma işlemini başlatır"""
        print(f"Satır {row_index + 1} için koordinat alma işlemi başlatıldı")
        # Bu metodu kullanarak koordinat alma işlemi başlatılır
        # Gerçek koordinat alma işlemi ana pencere tarafından yapılacak
    
    def set_row_coordinates(self, row_index, x, y):
        """Satır için koordinatları ayarlar"""
        if 0 <= row_index < len(self.heal_rows):
            row = self.heal_rows[row_index]
            
            # İlk nokta
            if len(row.coords) < 2:
                row.coords = [x, y]
                row.set_coordinates(row.coords)
                print(f"Satır {row_index + 1} için ilk koordinat ayarlandı: ({x}, {y})")
                
                # Statusbar mesajını göster
                if self.statusbar:
                    self.statusbar.showMessage(f"Satır {row_index + 1} için ilk koordinat ayarlandı. Şimdi ikinci koordinatı seçin.", 3000)
            # İkinci nokta
            else:
                row.coords.extend([x, y])
                row.set_coordinates(row.coords)
                print(f"Satır {row_index + 1} için ikinci koordinat ayarlandı: ({x}, {y})")
                
                # Statusbar mesajını göster
                if self.statusbar:
                    self.statusbar.showMessage(f"Satır {row_index + 1} için tüm koordinatlar ayarlandı.", 3000)

    def save_buffs(self):
        """Eklenmiş tüm buffları bir JSON dosyasına kaydeder"""
        try:
            # Başlangıç log mesajı 
            print("Buff verilerini toplama ve kaydetme işlemi başlatıldı")
            
            # Buff verilerini topla
            buffs_to_save = []
            
            # QListWidget'ta kaç öğe var?
            buff_count = self.buffs_list.count()
            if buff_count == 0:
                # Buff listesi boş
                self.statusbar.showMessage("Kaydedilecek buff bulunamadı!", 3000)
                print("Buff listesi boş, kaydedilecek veri yok.")
                return
                
            # QListWidget içindeki buff widget'larını topla
            for i in range(buff_count):
                item = self.buffs_list.item(i)
                widget = self.buffs_list.itemWidget(item)
                if widget:
                    # Widget'tan veriler
                    name_label = widget.findChild(QLabel, "buff_name")
                    duration_label = widget.findChild(QLabel, "buff_duration")
                    coordinates_label = widget.findChild(QLabel, "buff_coordinates")
                    active_checkbox = widget.findChild(QCheckBox, "buff_active")
                    
                    if not all([name_label, duration_label, coordinates_label, active_checkbox]):
                        print(f"Uyarı: Widget #{i+1} için bir veya daha fazla UI öğesi bulunamadı - atlanıyor")
                        continue
                        
                    # Verileri parse et
                    name = name_label.text().replace("İsim: ", "")
                    duration = int(duration_label.text().replace("Süre: ", "").replace(" sn", ""))
                    coord_text = coordinates_label.text().replace("Koordinatlar: ", "")
                    x, y = map(int, coord_text.split(","))
                    active = active_checkbox.isChecked()
                    
                    # Veri doğrulama
                    if not name or duration <= 0 or x < 0 or y < 0:
                        print(f"Uyarı: Widget #{i+1} için geçersiz veriler tespit edildi - atlanıyor")
                        continue
                    
                    # Buff verisini oluştur
                    buff_data = {
                        "name": name,
                        "duration": duration,
                        "coordinates": [x, y],
                        "active": active
                    }
                    
                    buffs_to_save.append(buff_data)
                    print(f"Buff eklendi: {name}, Süre: {duration}s, Koordinatlar: ({x},{y}), Aktif: {active}")
            
            # Buff sayısını kontrol et
            if len(buffs_to_save) == 0:
                self.statusbar.showMessage("Geçerli buff bulunamadı, dosya kaydedilmedi!", 3000)
                print("Geçerli buff bulunamadı, kayıt işlemi iptal edildi.")
                return
            
            # JSON dosyasına kaydet
            import json
            import os
            
            # Dosya yolu
            buff_file = "buffs.json"
            backup_file = "buffs_backup.json"
            
            # Yedek oluştur (eğer mevcut dosya varsa)
            if os.path.exists(buff_file):
                # Önceki yedek varsa sil
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                
                # Mevcut dosyayı yedekle
                os.rename(buff_file, backup_file)
                print(f"Mevcut '{buff_file}' dosyası '{backup_file}' olarak yedeklendi.")
            
            # Yeni dosyaya kaydet
            with open(buff_file, "w", encoding="utf-8") as f:
                json.dump(buffs_to_save, f, ensure_ascii=False, indent=4)
            
            # Durum çubuğuna mesaj göster
            count_msg = f"{len(buffs_to_save)} buff başarıyla kaydedildi!"
            self.statusbar.showMessage(count_msg, 3000)
            print(f"{count_msg} ('{buff_file}' dosyasına)")
            
        except Exception as e:
            error_msg = f"Bufflar kaydedilirken hata oluştu: {str(e)}"
            self.statusbar.showMessage(error_msg, 3000)
            print(f"Kritik hata: {error_msg}")
            import traceback
            print(f"Hata detayları: {traceback.format_exc()}")
            
            # Kullanıcıya ayrıntılı hata mesajı göster
            QMessageBox.critical(self, "Kaydetme Hatası", 
                               f"{error_msg}\n\nLütfen daha sonra tekrar deneyin.")
    
    def load_buffs(self):
        """JSON dosyasından buffları yükler"""
        try:
            # Başlangıç log mesajı
            print("Buff verilerini yükleme işlemi başlatıldı")
            
            import json
            import os
            
            # Dosya yolları
            buff_file = "buffs.json"
            backup_file = "buffs_backup.json"
            
            # Dosya yoksa çık
            if not os.path.exists(buff_file):
                # Yedek dosyaya bak
                if os.path.exists(backup_file):
                    reply = QMessageBox.question(self, "Yedek Dosya Bulundu", 
                                               "Asıl dosya bulunamadı, ancak yedek mevcut.\n\nYedek dosyadan yüklemek ister misiniz?",
                                               QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                    if reply == QMessageBox.Yes:
                        buff_file = backup_file
                        print("Kullanıcı yedek dosyadan yüklemeyi kabul etti.")
                    else:
                        self.statusbar.showMessage("Yükleme işlemi iptal edildi.", 3000)
                        print("Kullanıcı yedek dosyadan yüklemeyi reddetti.")
                        return
                else:
                    self.statusbar.showMessage("Kayıtlı buff bulunamadı!", 3000)
                    print("Yüklenecek dosya bulunamadı: Ne asıl ne de yedek dosya mevcut.")
                    return
            
            # JSON dosyasından verileri oku
            with open(buff_file, "r", encoding="utf-8") as f:
                try:
                    buffs_data = json.load(f)
                except json.JSONDecodeError as json_err:
                    error_msg = f"Dosya geçerli bir JSON formatı değil: {str(json_err)}"
                    self.statusbar.showMessage(error_msg, 3000)
                    print(f"JSON ayrıştırma hatası: {error_msg}")
                    
                    # Yedek dosya dene
                    if buff_file != backup_file and os.path.exists(backup_file):
                        reply = QMessageBox.question(self, "Dosya Hatalı", 
                                                   f"Buff dosyası bozulmuş görünüyor.\n\nYedek dosyadan yüklemeyi denemek ister misiniz?",
                                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                        if reply == QMessageBox.Yes:
                            with open(backup_file, "r", encoding="utf-8") as backup:
                                try:
                                    buffs_data = json.load(backup)
                                    print("Yedek dosyadan veriler başarıyla yüklendi.")
                                except:
                                    self.statusbar.showMessage("Yedek dosya da bozuk!", 3000)
                                    print("Yedek dosya da geçerli JSON formatında değil.")
                                    return
                        else:
                            return
                    else:
                        return
            
            # Veri türü kontrolü
            if not isinstance(buffs_data, list):
                self.statusbar.showMessage("Buff dosyası geçersiz format içeriyor!", 3000)
                print(f"Geçersiz veri formatı: Beklenen liste, alınan {type(buffs_data)}")
                return
            
            # Mevcut buff listesini temizle
            self.buffs_list.clear()
            
            # Yüklenecek geçerli buff sayacı
            valid_buff_count = 0
            
            # Her bir buff için yeni bir widget ekle
            for i, buff in enumerate(buffs_data):
                try:
                    # Gerekli alanları içeriyor mu?
                    required_fields = ["name", "duration", "coordinates", "active"]
                    if not all(field in buff for field in required_fields):
                        print(f"Eksik alan(lar) içeren buff #{i+1} atlanıyor")
                        continue
                    
                    # Veri tipleri doğru mu?
                    if not isinstance(buff["name"], str) or not isinstance(buff["duration"], (int, float)):
                        print(f"Geçersiz veri tipi içeren buff #{i+1} atlanıyor")
                        continue
                        
                    # Koordinatlar listesi/tuple mı ve 2 elemanlı mı?
                    if not isinstance(buff["coordinates"], (list, tuple)) or len(buff["coordinates"]) != 2:
                        print(f"Geçersiz koordinat formatı içeren buff #{i+1} atlanıyor")
                        continue
                    
                    # Koordinatları tuple'a dönüştür
                    coords = tuple(buff["coordinates"])
                    
                    # Yeni buff widget'ı oluştur ve listeye ekle
                    result = self.add_buff_to_list(buff["name"], buff["duration"], coords, buff["active"])
                    if result:
                        valid_buff_count += 1
                        
                except Exception as item_err:
                    print(f"Buff #{i+1} yüklenirken hata oluştu, atlanıyor: {str(item_err)}")
                    continue
            
            # Yükleme sonucunu göster
            if valid_buff_count > 0:
                success_msg = f"{valid_buff_count} buff başarıyla yüklendi!"
                self.statusbar.showMessage(success_msg, 3000)
                print(f"{success_msg} (Toplam {len(buffs_data)} bufftan)")
            else:
                self.statusbar.showMessage("Geçerli bir buff yüklenemedi!", 3000)
                print("Hiçbir geçerli buff yüklenemedi.")
            
        except Exception as e:
            error_msg = f"Bufflar yüklenirken hata oluştu: {str(e)}"
            self.statusbar.showMessage(error_msg, 3000)
            print(f"Kritik hata: {error_msg}")
            import traceback
            print(f"Hata detayları: {traceback.format_exc()}")
            
            # Kullanıcıya ayrıntılı hata mesajı göster
            QMessageBox.critical(self, "Yükleme Hatası", 
                               f"{error_msg}\n\nBuff listesi sıfırlandı.")
    
    def add_buff_to_list(self, name=None, duration=60, coordinates=(0, 0), active=True):
        """
        Listeye yeni bir buff ekler. Parametreler sağlanmazsa kullanıcıdan bilgi alınır.
        
        :param name: Buff adı (None ise mevcut input alanından alınır)
        :param duration: Buff süresi (saniye)
        :param coordinates: (x, y) koordinat çifti
        :param active: Aktif mi?
        :return: Eklenen item veya None (hata durumunda)
        """
        try:
            # Başlangıç log mesajı
            print(f"Yeni buff ekleme işlemi başlatıldı: İsim={name}, Süre={duration}, Koordinatlar={coordinates}")
            
            # İsim kontrolü
            if name is None:
                name = self.buff_name_input.text().strip()
            
            # Basit doğrulama
            if not name:
                self.statusbar.showMessage("Buff adı boş olamaz!", 3000)
                print("Doğrulama hatası: Buff adı boş")
                return None
            
            if duration <= 0:
                self.statusbar.showMessage("Buff süresi pozitif olmalıdır!", 3000)
                print("Doğrulama hatası: Geçersiz süre değeri")
                return None
            
            if not isinstance(coordinates, (list, tuple)) or len(coordinates) != 2:
                self.statusbar.showMessage("Geçersiz koordinat formatı!", 3000)
                print("Doğrulama hatası: Geçersiz koordinat formatı")
                return None
            
            # Widget oluşturma ve yapılandırma
            item = QListWidgetItem()
            widget = QWidget()
            layout = QVBoxLayout(widget)
            
            # İsim etiketi
            name_label = QLabel(f"İsim: {name}")
            name_label.setObjectName("buff_name")
            layout.addWidget(name_label)
            
            # Süre etiketi
            duration_label = QLabel(f"Süre: {duration} sn")
            duration_label.setObjectName("buff_duration")
            layout.addWidget(duration_label)
            
            # Koordinat etiketi
            coord_label = QLabel(f"Koordinatlar: {coordinates[0]},{coordinates[1]}")
            coord_label.setObjectName("buff_coordinates")
            layout.addWidget(coord_label)
            
            # Aktif checkbox
            active_checkbox = QCheckBox("Aktif")
            active_checkbox.setObjectName("buff_active")
            active_checkbox.setChecked(active)
            # Aktif durumu değiştiğinde buffları kaydet
            active_checkbox.stateChanged.connect(lambda: self.save_buffs())
            layout.addWidget(active_checkbox)
            
            # İtemi listeye ekle ve widget'ı ata
            self.buffs_list.addItem(item)
            item.setSizeHint(widget.sizeHint())
            self.buffs_list.setItemWidget(item, widget)
            
            # Input alanını temizle
            self.buff_name_input.clear()
            
            # Buffları kaydet
            self.save_buffs()
            
            # Kullanıcıya bilgi ver
            success_msg = f"'{name}' buff'ı başarıyla eklendi! Süre: {duration}s"
            self.statusbar.showMessage(success_msg, 3000)
            print(f"Buff eklendi: {name}, Süre: {duration}, Koordinatlar: {coordinates}, Aktif: {active}")
            
            return item
            
        except Exception as e:
            error_msg = f"Buff eklenirken hata oluştu: {str(e)}"
            self.statusbar.showMessage(error_msg, 3000)
            print(f"Kritik hata: {error_msg}")
            import traceback
            print(f"Hata detayları: {traceback.format_exc()}")
            return None

    def pick_buff_coordinates(self, item):
        """
        Seçilen buff için kullanıcıdan yeni koordinat seçmesini ister.
        
        :param item: Güncellenecek QListWidgetItem
        """
        try:
            # Mevcut widget'ı al
            widget = self.buffs_list.itemWidget(item)
            if not widget:
                self.statusbar.showMessage("Widget bulunamadı!", 3000)
                return
            
            # Koordinat etiketi
            coord_label = widget.findChild(QLabel, "buff_coordinates")
            if not coord_label:
                self.statusbar.showMessage("Koordinat etiketi bulunamadı!", 3000)
                return
            
            # Kullanıcıya bilgi ver
            self.statusbar.showMessage("Koordinat seçmek için 3 saniye içinde hedef noktaya tıklayın...", 3000)
            print("Koordinat seçimi bekleniyor...")
            
            # Ana pencereyi küçült
            self.showMinimized()
            
            # 3 saniye bekle
            QTimer.singleShot(3000, lambda: self._capture_coordinates_for_buff(item, coord_label))
            
        except Exception as e:
            error_msg = f"Koordinat seçimi başlatılırken hata: {str(e)}"
            self.statusbar.showMessage(error_msg, 3000)
            print(f"Hata: {error_msg}")

    def _capture_coordinates_for_buff(self, item, coord_label):
        """
        Fare ile koordinat seç ve buff'ı güncelle.
        
        :param item: Güncellenecek QListWidgetItem
        :param coord_label: Koordinat QLabel'ı
        """
        try:
            # Fare pozisyonunu al
            import pyautogui
            x, y = pyautogui.position()
            
            # Koordinat metnini güncelle
            coord_label.setText(f"Koordinatlar: {x},{y}")
            
            # Pencereyi geri göster
            self.showNormal()
            
            # Buffları kaydet
            self.save_buffs()
            
            # Kullanıcıya bilgi ver
            self.statusbar.showMessage(f"Yeni koordinatlar seçildi: ({x}, {y})", 3000)
            print(f"Buff koordinatları güncellendi: ({x}, {y})")
            
        except Exception as e:
            self.showNormal()
            error_msg = f"Koordinat yakalanırken hata: {str(e)}"
            self.statusbar.showMessage(error_msg, 3000)
            print(f"Hata: {error_msg}")

    def remove_buff(self, item):
        """
        Verilen itemi buff listesinden kaldırır.
        
        :param item: Kaldırılacak QListWidgetItem
        """
        try:
            # Widget'tan buff ismini al
            widget = self.buffs_list.itemWidget(item)
            if not widget:
                return
            
            name_label = widget.findChild(QLabel, "buff_name")
            buff_name = name_label.text().replace("İsim: ", "") if name_label else "Bilinmeyen"
            
            # İtemi listeden kaldır
            row = self.buffs_list.row(item)
            removed_item = self.buffs_list.takeItem(row)
            del removed_item
            
            # Buffları kaydet
            self.save_buffs()
            
            # Kullanıcıya bilgi ver
            self.statusbar.showMessage(f"'{buff_name}' buff'ı listeden kaldırıldı", 3000)
            print(f"Buff silindi: {buff_name}")
            
        except Exception as e:
            error_msg = f"Buff silinirken hata: {str(e)}"
            self.statusbar.showMessage(error_msg, 3000)
            print(f"Hata: {error_msg}")

if __name__ == "__main__":
    # Bu dosya doğrudan çalıştırıldığında test amaçlı olarak AutoHealUI penceresini gösterir
    # Normal kullanımda auto_heal_main.py üzerinden çalıştırılmalıdır
    try:
        print("Test Modu: AutoHealUI penceresi açılıyor...")
        print("Normal kullanım için auto_heal_main.py'ı çalıştırın.")
        app = QApplication(sys.argv)
        app.setStyle('Fusion')  # Modern görünüm için
        window = AutoHealUI()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Uygulama başlatılırken kritik hata: {e}") 