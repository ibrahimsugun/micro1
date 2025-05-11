import json
import os
import pyautogui
import random
import time
import numpy as np
from PyQt5.QtWidgets import QApplication, QComboBox, QWidget, QPushButton, QTabWidget, QLabel, QLineEdit, QSlider, QVBoxLayout, QHBoxLayout, QCheckBox, QMessageBox, QStackedWidget, QGridLayout, QSpinBox
from PyQt5.QtCore import Qt, pyqtSignal
import threading
from pynput.keyboard import Listener, Key
import mss
import string
from interception import *
import ctypes
import cv2
import configparser
import psutil
# Doğru modülden sınıfı içe aktar
from auto_heal_ui import AutoHealBuffWidget

def is_process_running(process_name):
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'].lower() == process_name.lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

class MainWindow(QWidget):
    information_signal = pyqtSignal(str)
    def __init__(self):
        super(MainWindow, self).__init__()
        self.information_signal.connect(self.information_changed)
        self.i = 0
        self.start_shortcut = ''
        self.screenshot = None
        self.config_file = "settings.ini"
        self.tuslar = []
        self.keyboard = None
        
        # Gelişmiş Auto Heal için özel değişkenler
        self.auto_heal_target_job = 0  # Koordinat alma işi için özel bir değer
        self.custom_screenshot = None  # Özel ekran görüntüsü için
        
        # Debug klasörünü oluştur
        self.debug_mode = False  # Debug modu varsayılan olarak kapalı
        if self.debug_mode:
            os.makedirs('images', exist_ok=True)
        
        self.keycodes = {"F1" : 0x3B,"F2" : 0x3C,"F3" : 0x3D,"F4" : 0x3E,"F5" : 0x3F,"F6" : 0x40,"F7" : 0x41,"F8" : 0x42,"F9" : 0x43,"F10" : 0x44,"F11" : 0x57,"F12" : 0x58,"F13" : 0x64,"F14" : 0x65,"F15" : 0x66,"0" : 0x0B,"1" : 0x02,"2" : 0x03,"3" : 0x04,"4" : 0x05,"5" : 0x06,"6" : 0x07,"7" : 0x08,"8" : 0x09,"9" : 0x0A,"A" : 0x1E,"B" : 0x30,"C" : 0x2E,"D" : 0x20,"E" : 0x12,"F" : 0x21,"G" : 0x22,"H" : 0x23,"I" : 0x17,"J" : 0x24,"K" : 0x25,"L" : 0x26,"M" : 0x32,"N" : 0x31,"O" : 0x18,"P" : 0x19,"Q" : 0x10,"R" : 0x13,"S" : 0x1F,"T" : 0x14,"U" : 0x16,"V" : 0x2F,"W" : 0x11,"X" : 0x2D,"Y" : 0x15,"Z" : 0x2C}
        
        # Hedef tespiti için değişkenler
        self.target_detection = False
        self.last_target_state = False
        self.target_locate = []  # Hedef çubuğunun konumu
        self.sct = mss.mss()
        
        # MagicHammer özelliği için değişkenler
        self.magic_hammer_active = False  # MagicHammer özelliği açık/kapalı
        self.magic_hammer_locate = []  # MagicHammer renk kontrolü yapılacak konum
        self.magic_hammer_shortcut = ''  # MagicHammer tuşu
        self.magic_hammer_last_used = 0  # Son MagicHammer kullanım zamanı
        self.magic_hammer_cooldown_ms = 5000  # Tekrar kullanım için bekleme süresi (5 saniye)
        self.magic_hammer_target_color = (53, 51, 172)  # Hedef renk - #AC3335'in BGR karşılığı
        self.magic_hammer_detection = False  # MagicHammer özelliği çalışıyor mu?
        
        try:
            self.driver = interception()
            for i in range(MAX_DEVICES):
                if interception.is_keyboard(i):
                    self.keyboard = i
                    print(f"Keyboard found: {i}")
                    break
            if self.keyboard == None:
                print("Keyboard not found.")
        except Exception as e:
            print(f"Interception sürücüsü yüklenirken hata: {e}")

        # HP/MP ile ilgili değişkenler
        self.heal_locate = []  # HP barının konumu
        self.heal_min = 15     # HP minimum seviye
        self.heal_shortcut = ''  # HP potu kısayolu
        self.mana_locate = []  # MP barının konumu
        self.mana_min = 15     # MP minimum seviye
        self.mana_shortcut = ''  # MP potu kısayolu
        self.oto_heal = False  # Otomatik HP kullanımı açık/kapalı
        self.oto_mana = False  # Otomatik MP kullanımı açık/kapalı
        self.oto_heal_mana_ms = 100  # HP/MP kontrolü için bekleme süresi (ms)
        
        # Makro ile ilgili değişkenler
        self.Makro_use_continuously_bool = False  # Sürekli kullanım açık/kapalı
        self.Makro_using = False  # Makro kullanılıyor mu?
        self.Makro_use = True     # Makro özelliği açık/kapalı
        
        # Makro tuşları için değişkenler - varsayılan değerler
        self.Makro_keys_list = ['', '', '', '']  # 4 adet makro tuşu için liste
        self.Makro_delays_list = [100, 100, 100, 100]  # Her tuş için bekleme süresi (ms)
        
        # İş ve durum takibi için değişkenler
        self.target_job = 0  # Aktif hedef işlemi
        self.working = False  # Çalışma durumu
        
        # Tuş dinleyicisini başlat
        self.start_key_listener()
        
        # Arayüzü oluştur
        self.Ui()
        self.apply_dark_theme()

    def apply_dark_theme(self):
        dark_theme = """
        QWidget {
            background-color: #2E2E2E;
            color: #FFFFFF;
            font-size: 14px;
            font-family: Arial, sans-serif;
        }
        QLineEdit {
            background-color: #3E3E3E;
            color: #FFFFFF;
            border: 1px solid #5A5A5A;
            border-radius: 4px;
            padding: 1px;
        }
        QLineEdit:disabled {
            background-color: #2E2E2E;
            border: 1px solid #4E4E4E;
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
        }
        QPushButton:hover {
            background-color: #5A5A5A;
        }
        QPushButton:pressed {
            background-color: #1E1E1E;
        }
        QLabel {
            color: #FFFFFF;
        }
        QTabWidget::pane {
            border: 1px solid #5A5A5A;
            background-color: #2E2E2E;
        }
        QTabBar::tab {
            background: #3E3E3E;
            color: #FFFFFF;
            border: 1px solid #5A5A5A;
            border-radius: 4px;
            padding: 5px;
        }
        QTabBar::tab:selected {
            background: #5A5A5A;
        }
        QVBoxLayout, QHBoxLayout {
            border: none;
        }
        QCheckBox {
            font-size: 16px;
            padding: 10px;
        }
        QCheckBox::indicator:unchecked:disabled {
            background-color: #3E3E3E;
        }
        QCheckBox::indicator:checked:disabled {
            background-color: #5A5A5A;
        }
        """
        self.setStyleSheet(dark_theme)

    def random_name(self, length=8):
        letters = string.ascii_letters
        return ''.join(random.choice(letters) for _ in range(length))

    def Ui(self):
        self.isim = self.random_name()
        self.setWindowTitle(self.isim)
        self.setGeometry(100, 100, 450, 700)  # Biraz daha geniş pencere

        # Ana tab widget
        self.tab_widget = QTabWidget()
        
        # Tab 1: Orijinal arayüz
        self.original_tab = QWidget()
        self.setup_original_tab()
        self.tab_widget.addTab(self.original_tab, "Temel")
        
        # Tab 2: Gelişmiş Auto Heal ve Buff sistemi
        self.auto_heal_buff_tab = QWidget()
        self.setup_auto_heal_buff_tab()
        self.tab_widget.addTab(self.auto_heal_buff_tab, "Oto Heal + Buff")
        
        # Ana layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tab_widget)
        self.setLayout(main_layout)

    def setup_original_tab(self):
        """Orijinal arayüzü oluşturur."""
        # Buttons and controls from both programs
        self.saveButton = QPushButton("Kaydet")
        self.saveButton.clicked.connect(self.save_config)
        self.saveButton.setToolTip("Tüm ayarları kaydeder. Kaydedilen ayarlar config.json dosyasına yazılır.")

        self.loadButton = QPushButton("Yükle")
        self.loadButton.clicked.connect(self.load_config)
        self.loadButton.setToolTip("Kaydedilmiş ayarları config.json dosyasından yükler.")

        self.resetButton = QPushButton("Sıfırla")
        self.resetButton.clicked.connect(self.reset_config)
        self.resetButton.setToolTip("Tüm ayarları varsayılan değerlerine döndürür.")

        self.start_stop_shortcut_buton = QPushButton("Başlat/Durdur")
        self.start_stop_shortcut_buton.clicked.connect(self.start_stop_shortcut_clicked)
        self.start_stop_shortcut_buton.setToolTip("Makroyu başlatmak/durdurmak için kullanılacak kısayol tuşunu belirler.")

        # Heal/Mana Controls
        self.take_heal_locate = QPushButton("HP Kordinatlarını Al")
        self.take_heal_locate.clicked.connect(self.take_heal_locate_pressed)
        self.take_heal_locate.setToolTip("HP barının konumunu belirlemek için fareyi HP barının üzerine getirin ve CTRL tuşuna basın.")
        
        self.take_mana_locate = QPushButton("MP Kordinatlarını Al")
        self.take_mana_locate.clicked.connect(self.take_mana_locate_pressed)
        self.take_mana_locate.setToolTip("MP barının konumunu belirlemek için fareyi MP barının üzerine getirin ve CTRL tuşuna basın.")
        
        self.heal_shortcut_button = QPushButton("Hp")
        self.heal_shortcut_button.clicked.connect(self.heal_shortcut_clicked)
        self.heal_shortcut_button.setToolTip("HP potunu kullanmak için kısayol tuşunu belirler.")
        
        self.mana_shortcut_button = QPushButton("Mp")
        self.mana_shortcut_button.clicked.connect(self.mana_shortcut_clicked)
        self.mana_shortcut_button.setToolTip("MP potunu kullanmak için kısayol tuşunu belirler.")
        
        # MagicHammer Controls
        self.magic_hammer_checkbox = QCheckBox("MagicHammer")
        self.magic_hammer_checkbox.stateChanged.connect(self.magic_hammer_func)
        self.magic_hammer_checkbox.setToolTip("Belirtilen konumda #AC3335 rengi tespit edildiğinde otomatik olarak belirlenen tuşa basar.")
        
        self.take_magic_hammer_locate = QPushButton("MagicHammer Konumunu Al")
        self.take_magic_hammer_locate.clicked.connect(self.take_magic_hammer_locate_pressed)
        self.take_magic_hammer_locate.setToolTip("MagicHammer için izlenecek konumu seçmek için fareyi istenen noktaya getirin ve CTRL tuşuna basın. #AC3335 rengi otomatik olarak takip edilecektir.")
        
        self.magic_hammer_shortcut_button = QPushButton("MagicHammer")
        self.magic_hammer_shortcut_button.clicked.connect(self.magic_hammer_shortcut_clicked)
        self.magic_hammer_shortcut_button.setToolTip("MagicHammer için basılacak tuşu belirler.")

        # Checkboxes
        self.oto_heal_checkbox = QCheckBox("Oto-HP")
        self.oto_heal_checkbox.stateChanged.connect(self.oto_heal_func)
        self.oto_heal_checkbox.setToolTip("HP barı belirlenen seviyenin altına düştüğünde otomatik pot kullanır.")
        
        self.oto_mana_checkbox = QCheckBox("Oto-MP")
        self.oto_mana_checkbox.stateChanged.connect(self.oto_mana_func)
        self.oto_mana_checkbox.setToolTip("MP barı belirlenen seviyenin altına düştüğünde otomatik pot kullanır.")
        
        # HP/MP Kontrol Aralığı Ayarı
        self.oto_heal_mana_ms_label = QLabel("Kontrol Hızı (ms):")
        self.oto_heal_mana_ms_input = QSpinBox()
        self.oto_heal_mana_ms_input.setMinimum(10)
        self.oto_heal_mana_ms_input.setMaximum(1000)
        self.oto_heal_mana_ms_input.setValue(self.oto_heal_mana_ms)
        self.oto_heal_mana_ms_input.valueChanged.connect(self.oto_heal_mana_ms_changed)
        self.oto_heal_mana_ms_input.setToolTip("HP/MP barlarının kontrol edilme aralığı (milisaniye). Düşük değerler daha hızlı tepki verir fakat daha fazla CPU kullanır.")

        # Combo boxes
        self.oto_heal_page = 'F Sayfası'
        self.oto_heal_page_combo_box = QComboBox()
        self.oto_heal_page_combo_box.addItems(['F Sayfası','F1','F2','F3','F4','F5','F6','F7','F8','F9','F10','F11','F12'])
        self.oto_heal_page_combo_box.currentTextChanged.connect(self.oto_heal_page_combo_box_changed)
        self.oto_heal_page_combo_box.setToolTip("HP potu kullanmadan önce geçilecek F tuşu sayfasını belirler. 'F Sayfası' seçilirse sayfa değiştirilmez.")
        
        self.oto_mana_page = 'F Sayfası'
        self.oto_mana_page_combo_box = QComboBox()
        self.oto_mana_page_combo_box.addItems(['F Sayfası','F1','F2','F3','F4','F5','F6','F7','F8','F9','F10','F11','F12'])
        self.oto_mana_page_combo_box.currentTextChanged.connect(self.oto_mana_page_combo_box_changed)
        self.oto_mana_page_combo_box.setToolTip("MP potu kullanmadan önce geçilecek F tuşu sayfasını belirler. 'F Sayfası' seçilirse sayfa değiştirilmez.")

        # Makro Tuşları ve Bekleme Süreleri
        self.Makro_keys_slots_label = QLabel("Makro Tuşları:")
        
        # Makro tuş slotları ve bekleme süreleri için düzen
        self.Makro_slots_layout = QGridLayout()
        self.Makro_slots_layout.setColumnStretch(0, 1)  # Tuş alanı
        self.Makro_slots_layout.setColumnStretch(1, 2)  # Bekleme süresi alanı
        
        self.Makro_key_inputs = []
        self.Makro_delay_inputs = []
        
        for i in range(4):
            # Tuş alanı
            key_input = QLineEdit()
            key_input.setText(self.Makro_keys_list[i])
            key_input.setToolTip(f"Slot {i+1} için makro tuşunu girin")
            key_input.setMaxLength(2)  # Maksimum 2 karakter (F1, F2 vb.)
            key_input.textChanged.connect(lambda text, idx=i: self.Makro_key_slot_changed(text, idx))
            self.Makro_key_inputs.append(key_input)
            
            # Bekleme süresi alanı
            delay_label = QLabel(f"Bekleme {i+1}:")
            delay_input = QLineEdit()
            delay_input.setText(str(self.Makro_delays_list[i] / 1000.0))
            delay_input.setToolTip(f"Slot {i+1} için bekleme süresi (saniye, maksimum 60 saniye)")
            delay_input.textChanged.connect(lambda value, idx=i: self.Makro_delay_slot_changed(value, idx))
            self.Makro_delay_inputs.append(delay_input)
            
            # Layout'a ekle
            self.Makro_slots_layout.addWidget(key_input, i, 0)
            self.Makro_slots_layout.addWidget(delay_label, i, 1)
            self.Makro_slots_layout.addWidget(delay_input, i, 2)
        
        self.Makro_use_continuously = QCheckBox("Sürekli kullan")
        self.Makro_use_continuously.stateChanged.connect(self.Makro_use_continuously_func)
        self.Makro_use_continuously.setToolTip("İşaretlenirse makro sürekli çalışır, işaretlenmezse bir kere çalışıp durur.")
        
        self.Makro_use_checkbox = QCheckBox("Makro Kullan")
        self.Makro_use_checkbox.stateChanged.connect(self.Makro_use_func)
        self.Makro_use_checkbox.setToolTip("Makroyu aktif/pasif yapar.")

        # Hedef Çubuğu Butonu
        self.take_target_locate = QPushButton("Hedef Çubuğu Konumu Al")
        self.take_target_locate.clicked.connect(self.take_target_locate_pressed)
        self.take_target_locate.setToolTip("Hedef çubuğunun sol üst köşesine tıklayın ve CTRL tuşuna basın. Bu konum hedef tespiti için kullanılacak.")

        self.setup_layout_original()

    def setup_auto_heal_buff_tab(self):
        """Gelişmiş Auto Heal ve Buff sisteminin arayüzünü oluşturur."""
        layout = QVBoxLayout()
        
        # Auto Heal ve Buff widget'ını ekle
        self.auto_heal_buff_widget = AutoHealBuffWidget(self)
        layout.addWidget(self.auto_heal_buff_widget)
        
        # Ayarları yükle/kaydet ve başlat/durdur butonları
        control_layout = QHBoxLayout()
        
        self.auto_heal_buff_start_button = QPushButton("Başlat")
        self.auto_heal_buff_start_button.clicked.connect(self.auto_heal_buff_start)
        self.auto_heal_buff_start_button.setStyleSheet("background-color: #387040; color: #FFFFFF;")
        
        self.auto_heal_buff_stop_button = QPushButton("Durdur")
        self.auto_heal_buff_stop_button.clicked.connect(self.auto_heal_buff_stop)
        self.auto_heal_buff_stop_button.setStyleSheet("background-color: #702F2F; color: #FFFFFF;")
        
        self.auto_heal_buff_save_button = QPushButton("Ayarları Kaydet")
        self.auto_heal_buff_save_button.clicked.connect(self.save_config)
        
        control_layout.addWidget(self.auto_heal_buff_start_button)
        control_layout.addWidget(self.auto_heal_buff_stop_button)
        control_layout.addWidget(self.auto_heal_buff_save_button)
        
        layout.addLayout(control_layout)
        
        # Bilgi metni
        info_label = QLabel("Koordinatları almak için ilgili satır butonuna tıklayın, ardından CTRL tuşunu kullanarak HP barının SOL ve SAĞ noktalarını işaretleyin.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #AAAAAA; margin-top: 10px;")
        layout.addWidget(info_label)
        
        self.auto_heal_buff_tab.setLayout(layout)

    def setup_layout_original(self):
        """Orijinal arayüz için layout kurar."""
        main_layout = QVBoxLayout()
        
        # Heal/Mana Section
        heal_mana_group = QVBoxLayout()
        
        # Heal Controls
        heal_layout = QVBoxLayout()
        heal_layout.addWidget(self.oto_heal_checkbox)
        heal_layout.addWidget(self.take_heal_locate)
        heal_buttons = QHBoxLayout()
        heal_buttons.addWidget(self.oto_heal_page_combo_box)
        heal_buttons.addWidget(self.heal_shortcut_button)
        heal_layout.addLayout(heal_buttons)
        
        # Mana Controls
        mana_layout = QVBoxLayout()
        mana_layout.addWidget(self.oto_mana_checkbox)
        mana_layout.addWidget(self.take_mana_locate)
        mana_buttons = QHBoxLayout()
        mana_buttons.addWidget(self.mana_shortcut_button)
        mana_buttons.addWidget(self.oto_mana_page_combo_box)
        mana_layout.addLayout(mana_buttons)
        
        # Combine Heal and Mana horizontally
        heal_mana_row = QHBoxLayout()
        heal_mana_row.addLayout(heal_layout)
        heal_mana_row.addLayout(mana_layout)
        heal_mana_group.addLayout(heal_mana_row)
        
        # HP/MP Kontrol Aralığı
        kontrol_araligi_layout = QHBoxLayout()
        kontrol_araligi_layout.addWidget(self.oto_heal_mana_ms_label)
        kontrol_araligi_layout.addWidget(self.oto_heal_mana_ms_input)
        heal_mana_group.addLayout(kontrol_araligi_layout)
        
        # MagicHammer Section
        magic_hammer_group = QVBoxLayout()
        
        # MagicHammer Info Label
        magic_hammer_info = QLabel("Seçilen konumda renk belirdiğinde otomatik tuşa basar (5sn bekleme)")
        magic_hammer_info.setWordWrap(True)
        magic_hammer_group.addWidget(magic_hammer_info)
        
        magic_hammer_group.addWidget(self.magic_hammer_checkbox)
        magic_hammer_group.addWidget(self.take_magic_hammer_locate)
        magic_hammer_group.addWidget(self.magic_hammer_shortcut_button)
        
        # Target Section
        target_group = QVBoxLayout()
        target_group.addWidget(self.take_target_locate)
        
        # Makro Section
        makro_group = QVBoxLayout()
        
        # Makro Input Row
        makro_input_row = QHBoxLayout()
        makro_input_row.addWidget(self.Makro_keys_slots_label)
        makro_group.addLayout(makro_input_row)
        
        # Makro Slots Section
        makro_group.addLayout(self.Makro_slots_layout)
        
        # Makro Checkboxes
        makro_checks = QHBoxLayout()
        makro_checks.addWidget(self.Makro_use_continuously)
        makro_checks.addWidget(self.Makro_use_checkbox)
        makro_group.addLayout(makro_checks)
        
        # Control Buttons Section
        control_buttons = QVBoxLayout()
        control_buttons.addWidget(self.start_stop_shortcut_buton)
        save_load = QHBoxLayout()
        save_load.addWidget(self.saveButton)
        save_load.addWidget(self.loadButton)
        save_load.addWidget(self.resetButton)
        control_buttons.addLayout(save_load)
        
        # Add all sections to main layout
        main_layout.addLayout(heal_mana_group)
        main_layout.addLayout(magic_hammer_group)
        main_layout.addLayout(target_group)
        main_layout.addLayout(makro_group)
        main_layout.addLayout(control_buttons)
        
        # Add contact information
        contact_label = QLabel()
        contact_label.setOpenExternalLinks(True)
        contact_label.setText("<a href='https://github.com/cgetiren/' style='color: white;'>iletişim: github/cgetiren</a>")
        main_layout.addWidget(contact_label)
        
        self.original_tab.setLayout(main_layout)

    def setup_layout(self):
        """Bu fonksiyon artık tab layout'unu ayarlar."""
        # Boş bir metot, layout artık Ui içinde kuruluyor

    def information_changed(self, text):
        QMessageBox.information(self, "Bilgi", text)

    def oto_heal_func(self):
        if self.oto_heal_checkbox.isChecked():
            self.oto_heal = True
        else:
            self.oto_heal = False

    def oto_mana_func(self):
        if self.oto_mana_checkbox.isChecked():
            self.oto_mana = True
        else:
            self.oto_mana = False

    def Makro_use_func(self):
        if self.Makro_use_checkbox.isChecked():
            self.Makro_use = True
        else:
            self.Makro_use = False

    def Makro_use_continuously_func(self):
        if self.Makro_use_continuously.isChecked():
            self.Makro_use_continuously_bool = True
        else:
            self.Makro_use_continuously_bool = False

    def Makro_key_slot_changed(self, text, index):
        """Makro tuş slotlarındaki değişiklikleri kaydeder."""
        if not self.working:
            try:
                self.Makro_keys_list[index] = text.upper()
                print(f"Makro slot {index+1} tuşu değiştirildi: {text.upper()}")
            except Exception as e:
                print(f"Makro tuş slotu değiştirme hatası: {e}")

    def Makro_delay_slot_changed(self, value, index):
        """Makro bekleme süresi slotlarındaki değişiklikleri kaydeder."""
        if not self.working:
            try:
                # Boş değer kontrolü
                if not value:
                    return
                
                # Ondalık değer dönüştürme
                delay_saniye = float(value.replace(',', '.'))
                
                # Maksimum 60 saniye kontrolü
                if delay_saniye > 60:
                    self.information_signal.emit("Maksimum bekleme süresi 60 saniye olabilir.")
                    delay_saniye = 60
                    self.Makro_delay_inputs[index].setText("60")
                
                # Milisaniyeye çevir ve kaydet
                delay_ms = int(delay_saniye * 1000)
                self.Makro_delays_list[index] = delay_ms
                print(f"Makro slot {index+1} bekleme süresi değiştirildi: {delay_saniye:.2f} saniye ({delay_ms} ms)")
            except ValueError:
                self.information_signal.emit("Geçerli bir sayı giriniz (örn: 1.5)")
                print(f"Makro bekleme süresi değiştirme hatası: Geçersiz değer")
            except Exception as e:
                print(f"Makro bekleme süresi değiştirme hatası: {e}")

    def oto_heal_page_combo_box_changed(self):
        if self.oto_heal_page_combo_box.currentText().lower() == self.start_shortcut:
            self.information_signal.emit("Bu başlat olarak kullanıldığından dolayı başka bir tuş seçmelisiniz.")
            self.oto_heal_page_combo_box.setCurrentText(self.oto_heal_page)
        else:
            self.oto_heal_page = self.oto_heal_page_combo_box.currentText()

    def oto_mana_page_combo_box_changed(self):
        if self.oto_mana_page_combo_box.currentText().lower() == self.start_shortcut:
            self.information_signal.emit("Bu başlat olarak kullanıldığından dolayı başka bir tuş seçmelisiniz.")
            self.oto_mana_page_combo_box.setCurrentText(self.oto_mana_page)
        else:
            self.oto_mana_page = self.oto_mana_page_combo_box.currentText()

    def start_stop_shortcut_clicked(self):
        if len(self.start_shortcut) == 0:
            self.target_job = 5
        elif len(self.start_shortcut) > 0:
            if self.start_shortcut in self.tuslar:
                self.tuslar.remove(self.start_shortcut)
            self.start_shortcut = ''
            self.start_stop_shortcut_buton.setText("Başlat/Durdur")

    def heal_shortcut_clicked(self):
        if len(self.heal_shortcut) == 0:
            self.target_job = 3
        elif len(self.heal_shortcut) > 0:
            self.heal_shortcut = ''
            self.heal_shortcut_button.setText("HP")

    def mana_shortcut_clicked(self):
        if len(self.mana_shortcut) == 0:
            self.target_job = 4
        elif len(self.mana_shortcut) > 0:
            self.mana_shortcut = ''
            self.mana_shortcut_button.setText("MP")

    def take_heal_locate_pressed(self):
        if len(self.heal_locate) == 0:
            self.target_job = 1
        elif len(self.heal_locate) > 0:
            self.heal_locate = []
            self.take_heal_locate.setText("HP Kordinatlarını Al")

    def take_mana_locate_pressed(self):
        if len(self.mana_locate) == 0:
            self.target_job = 2
        if len(self.mana_locate) > 0:
            self.mana_locate = []
            self.take_mana_locate.setText("MP Kordinatlarını Al")

    def take_target_locate_pressed(self):
        if len(self.target_locate) == 0:
            self.target_job = 6  # Yeni bir job numarası
        elif len(self.target_locate) > 0:
            self.target_locate = []
            self.take_target_locate.setText("Hedef Çubuğu Konumu Al")

    def take_target_screenshot(self):
        if len(self.target_locate) != 2:
            return None
        # Her seferinde yeni bir MSS nesnesi oluştur
        with mss.mss() as sct:
            # Hedef çubuğunun olduğu bölgenin ekran görüntüsünü al
            # Genişlik ve yüksekliği artırıyoruz ki hedef çubuğunu tam kapsasın
            monitor = {
                "top": max(0, self.target_locate[1] - 5),  # Biraz yukarıdan başla
                "left": max(0, self.target_locate[0] - 5),  # Biraz soldan başla
                "width": 400,  # Hedef çubuğunun tamamını kapsayacak genişlik
                "height": 50   # Hedef çubuğunun tamamını kapsayacak yükseklik
            }
            screenshot = np.array(sct.grab(monitor))
            
            # Debug modunda görüntüyü kaydet
            if self.debug_mode:
                cv2.imwrite(f'images/raw_screenshot_{time.time()}.jpg', screenshot)
            
            return cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

    def check_target(self):
        img = self.take_target_screenshot()
        if img is None:
            return False
            
        # Hedef çubuğunun rengini kontrol et
        # Knight Online'da hedef çubuğu genellikle kırmızı renktedir
        # BGR formatında: Kırmızı için düşük mavi(B) ve yeşil(G), yüksek kırmızı(R)
        red_mask = (
            (img[:, :, 0] < 100) &  # Düşük mavi
            (img[:, :, 1] < 100) &  # Düşük yeşil
            (img[:, :, 2] > 150)    # Yüksek kırmızı
        )
        
        # Kırmızı piksellerin sayısını kontrol et
        red_pixel_count = np.sum(red_mask)
        has_target = red_pixel_count > 100  # En az 100 kırmızı piksel varsa hedef var demektir
        
        # Debug modunda görüntüleri kaydet
        if self.debug_mode:
            timestamp = time.time()
            debug_img = img.copy()
            # Tespit edilen kırmızı alanları yeşil ile işaretle
            debug_img[red_mask] = [0, 255, 0]
            cv2.imwrite(f'images/debug_{timestamp}_pixels_{red_pixel_count}.jpg', debug_img)
        
        # Hedef durumu değişti mi kontrolü
        if has_target != self.last_target_state:
            print(f"Hedef durumu değişti: {'Var' if has_target else 'Yok'} (Kırmızı piksel sayısı: {red_pixel_count})")
        
        self.last_target_state = has_target
        return has_target

    def target_detection_helper(self):
        """
        Hedef çubuğunun durumunu düzenli aralıklarla kontrol eden thread fonksiyonu.
        Hedefin var olup olmadığını tespit eder.
        """
        # Hedef tespiti kontrol süresi (ms cinsinden)
        kontrol_suresi_ms = 100  # 100ms
        kontrol_suresi_saniye = kontrol_suresi_ms / 1000.0
        
        while self.working and self.target_detection:
            try:
                if len(self.target_locate) == 2:
                    # Hedef çubuğu konumundaki pikselin ekran görüntüsünü al
                    self.take_screenshot((self.target_locate[0], self.target_locate[1], 
                                          self.target_locate[0] + 1, self.target_locate[1] + 1))
                    rgb = self.screenshot[0, 0]
                    
                    # Hedef çubuğu genellikle kırmızı renktedir - renk kontrolü yap
                    onceki_durum = self.last_target_state
                    if rgb[2] > 200 and rgb[1] < 50 and rgb[0] < 50:  # Kırmızı renk kontrolü
                        self.last_target_state = True
                    else:
                        self.last_target_state = False
                        
                    # Hedef durumu değiştiyse bilgi ver
                    if onceki_durum != self.last_target_state:
                        print(f"Hedef durumu değişti: {'Var' if self.last_target_state else 'Yok'} - RGB değeri: {rgb}")
            except Exception as e:
                print(f"Hedef tespitinde hata: {e}")
                
            # Belirli aralıklarla kontrol et - CPU kullanımını optimize eder
            time.sleep(kontrol_suresi_saniye)

    def Makro(self):
        """
        Makro tuşlarını belirlenen sıra ve bekleme süreleriyle birlikte basan thread fonksiyonu.
        Her tuşa kendi bekleme süresi kadar basıp bekleme yapar.
        """
        while (self.working and self.Makro_use and self.Makro_using):
            # Makro tuş slotlarını kullan
            for i in range(4):
                if not (self.working and self.Makro_use and self.Makro_using):
                    break
                    
                # Slot boş değilse tuşu bas
                if self.Makro_keys_list[i]:
                    try:
                        # Tuşu bas
                        keycode = self.keycodes.get(self.Makro_keys_list[i], None)
                        if keycode:
                            print(f"Makro tuşu basılıyor: {self.Makro_keys_list[i]}")
                            # Tuşa basılı tutma süresi sabit 5ms (0.01 saniye)
                            tus_basma_suresi = 0.01  # 5ms
                            self.tusbas(keycode, tus_basma_suresi)
                            
                            # Tuşa özel bekleme süresi kadar bekle (ms -> saniye dönüşümü)
                            delay_ms = self.Makro_delays_list[i]
                            delay_saniye = delay_ms / 1000.0  # Milisaniyeyi saniyeye çevir
                            print(f"Tuş {self.Makro_keys_list[i]} için bekleme: {delay_ms}ms ({delay_saniye:.3f} saniye)")
                            time.sleep(delay_saniye)
                    except Exception as e:
                        print(f"Makro tuşu {self.Makro_keys_list[i]} basılırken hata: {e}")
            
            # Hedef yoksa Z tuşuna bas
            if len(self.target_locate) == 2 and not self.last_target_state:
                # Tuşa basılı tutma süresi sabit 5ms (0.01 saniye)
                self.tusbas(self.keycodes['Z'], 0.01)
                # Z tuşu için sabit 100ms bekleme (0.1 saniye)
                time.sleep(0.1)
            
            # Sürekli kullanım seçili değilse döngüyü bitir
            if not self.Makro_use_continuously_bool:
                self.working = False
                self.start_stop_shortcut_buton.setStyleSheet("background-color: #702F2F; color: #FFFFFF;")
                break

    def heal_mana_helper(self):
        """
        HP ve MP barlarını sürekli kontrol edip, belirli seviyenin altına düştüğünde 
        otomatik olarak pot kullanılmasını sağlayan thread fonksiyonu.
        """
        if len(self.heal_locate) == 2:
            sag_x_heal = self.heal_locate[0] + 1
            alt_y_heal = self.heal_locate[1] + 1
        else:
            sag_x_heal = self.mana_locate[0] - 1
            alt_y_heal = self.mana_locate[1] - 1
            
        if len(self.mana_locate) == 2:
            sag_x_mana = self.mana_locate[0] + 1
            alt_y_mana = self.mana_locate[1] + 1
        else:
            sag_x_mana = self.heal_locate[0] - 1
            alt_y_mana = self.heal_locate[1] - 1
            
        most_sol_x = 0
        most_sag_x = max(sag_x_heal, sag_x_mana)
        most_ust_y = 0
        most_alt_y = max(alt_y_heal, alt_y_mana)
        region = (most_sol_x, most_ust_y, most_sag_x - most_sol_x, most_alt_y - most_ust_y)
        
        # Heal/Mana kontrolü için bekleme süresi (ms cinsinden)
        kontrol_bekleme_ms = self.oto_heal_mana_ms
        kontrol_bekleme_saniye = kontrol_bekleme_ms / 1000.0
        
        while self.working and (self.oto_heal or self.oto_mana):
            self.take_screenshot(region, target=0)
            
            if self.oto_heal:
                rgb = self.heal_and_mana_screenshot[self.heal_locate[1], self.heal_locate[0]]
                if rgb[0] <= self.heal_min and rgb[1] <= self.heal_min and rgb[2] <= self.heal_min:
                    tus = self.heal_shortcut[1]
                    print(f"HP seviyesi düşük ({rgb}). HP potu kullanılıyor...")
                    
                    # Sayfa değiştirme gerekiyorsa
                    if self.oto_heal_page != 'F Sayfası':
                        # Tuşa basılı tutma süresi sabit 5ms (0.01 saniye)
                        self.tusbas(self.keycodes[self.oto_heal_page], 0.01)
                        # Sayfa değişimi için kısa bekleme
                        time.sleep(0.05)  # 50ms bekle
                        
                    # HP potunu kullan
                    self.tusbas(self.keycodes[tus], 0.01)
                    # Pot kullanımı sonrası kısa bekleme
                    time.sleep(0.05)  # 50ms bekle
                    
            if self.oto_mana:
                rgb = self.heal_and_mana_screenshot[self.mana_locate[1], self.mana_locate[0]]
                if rgb[0] <= self.mana_min and rgb[1] <= self.mana_min and rgb[2] <= self.mana_min:
                    tus = self.mana_shortcut[1]
                    print(f"MP seviyesi düşük ({rgb}). MP potu kullanılıyor...")
                    
                    # Sayfa değiştirme gerekiyorsa
                    if self.oto_mana_page != 'F Sayfası':
                        # Tuşa basılı tutma süresi sabit 5ms (0.01 saniye)
                        self.tusbas(self.keycodes[self.oto_mana_page], 0.01)
                        # Sayfa değişimi için kısa bekleme
                        time.sleep(0.05)  # 50ms bekle
                        
                    # MP potunu kullan
                    self.tusbas(self.keycodes[tus], 0.01)
                    # Pot kullanımı sonrası kısa bekleme
                    time.sleep(0.05)  # 50ms bekle
            
            # Her kontrol arasında bekleme süresi
            time.sleep(kontrol_bekleme_saniye)
            
        print("Heal/Mana kontrol döngüsü sonlandı.")

    def take_screenshot(self, region=None, target=None):
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            if region:
                monitor = {"top": region[1], "left": region[0], "width": region[2] - region[0], "height": region[3] - region[1]}
            screenshot = np.array(sct.grab(monitor))
            if target == None:
                self.screenshot = screenshot[:, :, :3].astype(np.uint8)
            elif target == 0:
                self.heal_and_mana_screenshot = screenshot[:, :, :3].astype(np.uint8)
            elif target == 2:  # Gelişmiş Oto Heal için custom hedef
                self.custom_screenshot = screenshot[:, :, :3].astype(np.uint8)

    def tusbas(self, key, gecikme):
        """
        Belirlenen tuşa basma ve bırakma işlemini gerçekleştiren fonksiyon.
        
        Parametreler:
            key (int): Basılacak tuşun keycode değeri
            gecikme (float): Tuşa basılı tutma süresi (saniye cinsinden)
        """
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

    def start_stop(self):
        if self.working == False:
            if self.oto_heal:
                if len(self.heal_locate) < 2:
                    self.information_signal.emit("Oto-HP kullanımı için HP Koordinatı belirlenmelidir.")
                    self.working = False
                    return
                if self.heal_shortcut == '':
                    self.information_signal.emit("Oto-HP kullanımı için HP belirlenmelidir.")
                    self.working = False
                    return
            if self.oto_mana:
                if len(self.mana_locate) < 2:
                    self.information_signal.emit("Oto-MP kullanımı için MP Koordinatı belirlenmelidir.")
                    self.working = False
                    return
                if self.mana_shortcut == '':
                    self.information_signal.emit("Oto-MP kullanımı için MP belirlenmelidir.")
                    self.working = False
                    return
            if self.magic_hammer_active:
                if len(self.magic_hammer_locate) < 2:
                    self.information_signal.emit("MagicHammer kullanımı için konum belirlenmelidir.")
                    self.working = False
                    return
                if self.magic_hammer_shortcut == '':
                    self.information_signal.emit("MagicHammer kullanımı için tuş belirlenmelidir.")
                    self.working = False
                    return
                    
            self.Makro_using = False
            
            self.working = True
            if self.Makro_use:
                self.Makro_using = True
                self.target_detection = True
                threading.Thread(target=self.Makro, daemon=True).start()
                threading.Thread(target=self.target_detection_helper, daemon=True).start()
            if self.oto_heal or self.oto_mana:
                threading.Thread(target=self.heal_mana_helper, daemon=True).start()
            if self.magic_hammer_active:
                self.magic_hammer_detection = True
                threading.Thread(target=self.magic_hammer_helper, daemon=True).start()
                
            self.start_stop_shortcut_buton.setStyleSheet("background-color: #387040; color: #FFFFFF;")
        elif self.working == True:
            self.working = False
            self.target_detection = False
            self.magic_hammer_detection = False
            self.start_stop_shortcut_buton.setStyleSheet("background-color: #702F2F; color: #FFFFFF;")

    def key_listener(self):
        self.pressed_keys = set()
        def on_press(key):
            if key in self.pressed_keys:
                return
            key_str = str(key)
            self.pressed_keys.add(key)

            def handle_target_job(button, list_name, message):
                x, y = pyautogui.position()
                list_name.append(x)
                list_name.append(y)
                button.setText(f"{message}")
                self.target_job = 0
                
                # Eğer MagicHammer konumu alınıyorsa, o noktadaki rengi de al
                if button == self.take_magic_hammer_locate:
                    try:
                        # Sabit renk kodunu ayarla (AC3335 için BGR: 53, 51, 172)
                        self.magic_hammer_target_color = (53, 51, 172)  # BGR format
                        hex_color = '#AC3335'
                        
                        print(f"MagicHammer için seçilen nokta ({x}, {y}), sabit renk kodu kullanılıyor: {hex_color}")
                        self.information_signal.emit(f"MagicHammer konumu ve rengi (#AC3335) ayarlandı")
                    except Exception as e:
                        print(f"MagicHammer ayarlanırken hata: {e}")

            def handle_shortcut(current_shortcut, key, button, action_name):
                if key == None:
                    self.information_signal.emit("Geçersiz bir tuş algılandı.")
                    return current_shortcut
                key_str = str(key)
                if key_str:
                    if key_str in self.tuslar:
                        self.information_signal.emit("Bu tuş zaten kullanılıyor.")
                    else:
                        current_shortcut = key_str
                        if not key_str.isnumeric():
                            if len(key_str) == 3:
                                if not key_str[1].isnumeric():
                                    key_str = key_str.lower()
                                    self.tuslar.append(key_str)
                            else:
                                key_str = key_str.lower()
                                self.tuslar.append(key_str)
                        self.target_job = 0
                        button.setText(f"{action_name} [{current_shortcut}]")
                else:
                    self.information_signal.emit("Geçersiz bir tuş algılandı.")
                return current_shortcut

            if key == Key.ctrl_l:
                # Gelişmiş Auto Heal için koordinat alma işlemleri (100-107 arası job'lar)
                if 100 <= self.auto_heal_target_job <= 107:
                    row = self.auto_heal_target_job - 100
                    # Koordinatları al
                    x, y = pyautogui.position()
                    # Auto Heal widget'ına bildir
                    self.auto_heal_buff_widget.set_row_coordinates(row, x, y)
                    # İşi sıfırla
                    if len(self.auto_heal_buff_widget.heal_rows[row]["coords"]) == 4:
                        self.auto_heal_target_job = 0
                
                # Mevcut koordinat alma işlemleri
                elif self.target_job == 1:
                    handle_target_job(self.take_heal_locate, self.heal_locate, "HP Kordinatları Alındı")
                elif self.target_job == 2:
                    handle_target_job(self.take_mana_locate, self.mana_locate, "MP Kordinatları Alındı")
                elif self.target_job == 6:  # Hedef çubuğu konumu için
                    handle_target_job(self.take_target_locate, self.target_locate, "Hedef Çubuğu Konumu Alındı")
                elif self.target_job == 7:  # MagicHammer konumu için
                    handle_target_job(self.take_magic_hammer_locate, self.magic_hammer_locate, "MagicHammer Konumu Alındı")
                
            # Diğer tuş işlemleri
            elif self.target_job == 3:
                self.heal_shortcut = handle_shortcut(self.heal_shortcut, key, self.heal_shortcut_button, "HP")
            elif self.target_job == 4:
                self.mana_shortcut = handle_shortcut(self.mana_shortcut, key, self.mana_shortcut_button, "MP")
            elif self.target_job == 5:
                self.start_shortcut = handle_shortcut(self.start_shortcut, key, self.start_stop_shortcut_buton, "Başlat/Durdur")
            elif self.target_job == 8:  # MagicHammer kısayolu için
                self.magic_hammer_shortcut = handle_shortcut(self.magic_hammer_shortcut, key, self.magic_hammer_shortcut_button, "MagicHammer")
            elif (key_str == self.start_shortcut):
                self.start_stop()

        def on_release(key):
            if key in self.pressed_keys:
                self.pressed_keys.remove(key)

        listener = Listener(on_press=on_press, on_release=on_release)
        listener.start()

    def start_key_listener(self):
        try:
            threading.Thread(target=self.key_listener, daemon=True).start()
        except Exception as e:
            pass

    def save_config(self):
        config = configparser.ConfigParser()
        config['Settings'] = {
            'oto_heal': str(self.oto_heal),
            'heal_locate': ','.join(map(str, self.heal_locate)),
            'heal_min': str(self.heal_min),
            'heal_shortcut': self.heal_shortcut,
            'oto_mana': str(self.oto_mana),
            'mana_locate': ','.join(map(str, self.mana_locate)),
            'mana_min': str(self.mana_min),
            'mana_shortcut': self.mana_shortcut,
            'makro_use': str(self.Makro_use),
            'makro_use_continuously': str(self.Makro_use_continuously_bool),
            'start_shortcut': self.start_shortcut,
            'oto_mana_page': self.oto_mana_page,
            'oto_heal_page': self.oto_heal_page,
            'target_locate': ','.join(map(str, self.target_locate)),
            # Makro tuşları ve bekleme süreleri
            'makro_keys_list': ','.join(self.Makro_keys_list),
            'makro_delays_list': ','.join(map(str, self.Makro_delays_list)),
            'oto_heal_mana_ms': str(self.oto_heal_mana_ms),
            # MagicHammer ayarları
            'magic_hammer_active': str(self.magic_hammer_active),
            'magic_hammer_locate': ','.join(map(str, self.magic_hammer_locate)),
            'magic_hammer_shortcut': self.magic_hammer_shortcut,
            'magic_hammer_cooldown_ms': str(self.magic_hammer_cooldown_ms)
        }
        
        # Gelişmiş Auto Heal ve Buff ayarlarını ekle
        config = self.auto_heal_buff_widget.save_config(config['Settings'])

        with open(self.config_file, 'w', encoding='utf-8') as f:
            config.write(f)
        QMessageBox.information(self, "Kaydedildi", "Ayarlar başarıyla kaydedildi.")

    def load_config(self):
        if not os.path.exists(self.config_file):
            QMessageBox.warning(self, "Hata", "Ayarlar dosyası bulunamadı.")
            return

        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        
        if 'Settings' in config:
            settings = config['Settings']
            self.oto_heal = settings.getboolean('oto_heal', False)
            self.heal_locate = [int(x) for x in settings.get('heal_locate', '').split(',') if x]
            self.heal_min = settings.getint('heal_min', 15)
            self.heal_shortcut = settings.get('heal_shortcut', '')
            self.oto_mana = settings.getboolean('oto_mana', False)
            self.mana_locate = [int(x) for x in settings.get('mana_locate', '').split(',') if x]
            self.mana_min = settings.getint('mana_min', 15)
            self.mana_shortcut = settings.get('mana_shortcut', '')
            self.Makro_use = settings.getboolean('makro_use', True)
            self.Makro_use_continuously_bool = settings.getboolean('makro_use_continuously', False)
            self.start_shortcut = settings.get('start_shortcut', '')
            self.oto_mana_page = settings.get('oto_mana_page', 'F Sayfası')
            self.oto_heal_page = settings.get('oto_heal_page', 'F Sayfası')
            self.target_locate = [int(x) for x in settings.get('target_locate', '').split(',') if x]
            
            # Makro tuşlarını ve bekleme sürelerini yükle
            makro_keys_list = settings.get('makro_keys_list', '')
            if makro_keys_list:
                self.Makro_keys_list = makro_keys_list.split(',')
                # Liste 4 eleman olana kadar boş string ekle
                while len(self.Makro_keys_list) < 4:
                    self.Makro_keys_list.append('')
            
            makro_delays_list = settings.get('makro_delays_list', '')
            if makro_delays_list:
                try:
                    self.Makro_delays_list = [int(x) for x in makro_delays_list.split(',') if x]
                    # Liste 4 eleman olana kadar 100ms ekle
                    while len(self.Makro_delays_list) < 4:
                        self.Makro_delays_list.append(100)
                except ValueError:
                    # Hata durumunda varsayılan değerler
                    self.Makro_delays_list = [100, 100, 100, 100]
            
            self.oto_heal_mana_ms = settings.getint('oto_heal_mana_ms', 100)
            
            # MagicHammer ayarlarını yükle
            self.magic_hammer_active = settings.getboolean('magic_hammer_active', False)
            self.magic_hammer_locate = [int(x) for x in settings.get('magic_hammer_locate', '').split(',') if x]
            self.magic_hammer_shortcut = settings.get('magic_hammer_shortcut', '')
            self.magic_hammer_cooldown_ms = settings.getint('magic_hammer_cooldown_ms', 5000)
            
            # Gelişmiş Auto Heal ve Buff ayarlarını yükle
            self.auto_heal_buff_widget.load_config(settings)
            
            self.fonksiyonlari_cagir()

    def fonksiyonlari_cagir(self):
        self.oto_heal_checkbox.setChecked(self.oto_heal)
        if len(self.heal_locate) > 0:
            self.take_heal_locate.setText("HP Koordinatı Alındı")
        if len(self.heal_shortcut) > 0:
            self.heal_shortcut_button.setText(f"HP [{self.heal_shortcut}]")
            self.tuslar.append(self.heal_shortcut)
        self.oto_mana_checkbox.setChecked(self.oto_mana)
        if len(self.mana_locate) > 0:
            self.take_mana_locate.setText("MP Koordinatı Alındı")
        if len(self.mana_shortcut) > 0:
            self.mana_shortcut_button.setText(f"MP [{self.mana_shortcut}]")
            self.tuslar.append(self.mana_shortcut)
        if len(self.start_shortcut) > 0:
            self.start_stop_shortcut_buton.setText(f"Başlat/Durdur [{self.start_shortcut}]")
            self.tuslar.append(self.start_shortcut)
        if self.oto_mana_page:
            self.oto_mana_page_combo_box.setCurrentText(self.oto_mana_page)
        if self.oto_heal_page:
            self.oto_heal_page_combo_box.setCurrentText(self.oto_heal_page)
        if len(self.target_locate) > 0:  # Hedef çubuğu konumu kontrolü eklendi
            self.take_target_locate.setText("Hedef Çubuğu Konumu Alındı")
        
        # MagicHammer ayarlarını yükle
        self.magic_hammer_checkbox.setChecked(self.magic_hammer_active)
        if len(self.magic_hammer_locate) > 0:
            self.take_magic_hammer_locate.setText("MagicHammer Konumunu Alındı")
        if len(self.magic_hammer_shortcut) > 0:
            self.magic_hammer_shortcut_button.setText(f"MagicHammer [{self.magic_hammer_shortcut}]")
            self.tuslar.append(self.magic_hammer_shortcut)
        
        # HP/MP kontrol aralığını güncelle
        self.oto_heal_mana_ms_input.setValue(self.oto_heal_mana_ms)
        
        # Yeni makro tuş ve bekleme sürelerini güncelle
        for i in range(len(self.Makro_key_inputs)):
            self.Makro_key_inputs[i].setText(self.Makro_keys_list[i])
            # Saniye cinsinden göster 
            delay_saniye = self.Makro_delays_list[i] / 1000.0
            self.Makro_delay_inputs[i].setText(f"{delay_saniye:.2f}")
        
        self.Makro_use_continuously.setChecked(self.Makro_use_continuously_bool)
        self.Makro_use_checkbox.setChecked(self.Makro_use)

    def is_knight_online_active(self):
        # Sadece process kontrolü yap
        return is_process_running("warfarex_64.exe")
        
    def reset_config(self):
        # Onay mesajı göster
        reply = QMessageBox.question(self, 'Onay', 
                                   'Tüm ayarları sıfırlamak istediğinizden emin misiniz?\nBu işlem geri alınamaz!',
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # HP/MP ayarlarını sıfırla
            self.oto_heal = False
            self.heal_locate = []
            self.heal_min = 15
            self.heal_shortcut = ''
            self.oto_mana = False
            self.mana_locate = []
            self.mana_min = 15
            self.mana_shortcut = ''
            self.oto_heal_mana_ms = 100  # HP/MP kontrol aralığı varsayılan değeri
            
            # MagicHammer ayarlarını sıfırla
            self.magic_hammer_active = False
            self.magic_hammer_locate = []
            self.magic_hammer_shortcut = ''
            self.magic_hammer_cooldown_ms = 5000
            
            # Makro ayarlarını sıfırla
            self.Makro_use_continuously_bool = False
            self.Makro_using = False
            self.Makro_use = True
            
            # Makro tuşlarını sıfırla
            self.Makro_keys_list = ['', '', '', '']
            self.Makro_delays_list = [100, 100, 100, 100]
            
            # Hedef tespiti ayarlarını sıfırla
            self.target_detection = False
            self.last_target_state = False
            self.target_locate = []
            
            # Başlat/Durdur tuşunu sıfırla
            self.start_shortcut = ''
            
            # F sayfası ayarlarını sıfırla
            self.oto_mana_page = 'F Sayfası'
            self.oto_heal_page = 'F Sayfası'
            
            # Tuş listesini temizle
            self.tuslar = []
            
            # UI'ı güncelle
            self.fonksiyonlari_cagir()
            
            # Butonları varsayılan metinlerine döndür
            self.take_heal_locate.setText("HP Kordinatlarını Al")
            self.take_mana_locate.setText("MP Kordinatlarını Al")
            self.heal_shortcut_button.setText("HP")
            self.mana_shortcut_button.setText("MP")
            self.start_stop_shortcut_buton.setText("Başlat/Durdur")
            self.take_target_locate.setText("Hedef Çubuğu Konumu Al")
            self.take_magic_hammer_locate.setText("MagicHammer Konumunu Al")
            self.magic_hammer_shortcut_button.setText("MagicHammer")
            
            # Kontrol aralığını varsayılan değerine döndür
            self.oto_heal_mana_ms_input.setValue(self.oto_heal_mana_ms)
            
            # Makro bekleme sürelerini sıfırla ve saniye formatında göster
            for i in range(len(self.Makro_delay_inputs)):
                delay_saniye = self.Makro_delays_list[i] / 1000.0
                self.Makro_delay_inputs[i].setText(f"{delay_saniye:.2f}")
            
            # Bilgi mesajı göster
            QMessageBox.information(self, "Bilgi", "Tüm ayarlar başarıyla sıfırlandı.")

    def oto_heal_mana_ms_changed(self, value):
        """
        HP/MP kontrol aralığı değiştiğinde çağrılan fonksiyon
        """
        self.oto_heal_mana_ms = value
        print(f"HP/MP kontrol aralığı değiştirildi: {value} ms")

    def magic_hammer_func(self):
        """
        MagicHammer özelliğinin açık/kapalı durumunu değiştirir.
        """
        if self.magic_hammer_checkbox.isChecked():
            if len(self.magic_hammer_locate) < 2:
                self.information_signal.emit("MagicHammer kullanımı için konum belirlenmelidir.")
                self.magic_hammer_checkbox.setChecked(False)
                return
            if self.magic_hammer_shortcut == '':
                self.information_signal.emit("MagicHammer kullanımı için tuş belirlenmelidir.")
                self.magic_hammer_checkbox.setChecked(False)
                return
                
            self.magic_hammer_active = True
            print("MagicHammer özelliği aktifleştirildi.")
            if not self.magic_hammer_detection:
                self.magic_hammer_detection = True
                threading.Thread(target=self.magic_hammer_helper, daemon=True).start()
        else:
            self.magic_hammer_active = False
            self.magic_hammer_detection = False
            print("MagicHammer özelliği devre dışı bırakıldı.")
            
    def take_magic_hammer_locate_pressed(self):
        """
        MagicHammer özelliği için izlenecek ekran konumunu belirlemek için buton işlevi.
        #AC3335 renk kodu otomatik olarak takip edilir.
        """
        if len(self.magic_hammer_locate) == 0:
            self.target_job = 7  # MagicHammer konumu için job numarası
            print("MagicHammer için konum seçin ve CTRL tuşuna basın. #AC3335 rengi otomatik olarak takip edilecektir.")
        elif len(self.magic_hammer_locate) > 0:
            self.magic_hammer_locate = []
            self.take_magic_hammer_locate.setText("MagicHammer Konumunu Al")
            
    def magic_hammer_shortcut_clicked(self):
        """
        MagicHammer için kullanılacak kısayol tuşunu belirlemek için buton işlevi.
        """
        if len(self.magic_hammer_shortcut) == 0:
            self.target_job = 8  # MagicHammer kısayolu için yeni job numarası
        elif len(self.magic_hammer_shortcut) > 0:
            self.magic_hammer_shortcut = ''
            self.magic_hammer_shortcut_button.setText("MagicHammer")
            
    def magic_hammer_helper(self):
        """
        Belirtilen konumda #AC3335 (BGR: 53, 51, 172) rengini sürekli kontrol edip, 
        bu renk tespit edildiğinde belirlenen kısayol tuşuna otomatik olarak basan thread fonksiyonu.
        Renk tespiti 20 birimlik bir tolerans ile yapılır.
        """
        print("MagicHammer kontrolü başladı. #AC3335 rengi takip ediliyor.")
        
        # Kontrol süresi ve renk toleransı
        kontrol_suresi_ms = 100  # 100ms
        kontrol_suresi_saniye = kontrol_suresi_ms / 1000.0
        renk_toleransi = 20  # RGB değerlerinde izin verilen sapma miktarı
        
        # Bekleme süresi 5 saniye (milisaniye cinsinden)
        bekleme_suresi_ms = 5000  # 5 saniye
        
        while self.working and self.magic_hammer_active and self.magic_hammer_detection:
            try:
                if len(self.magic_hammer_locate) == 2:
                    # Belirtilen konumdaki pikselin ekran görüntüsünü al
                    with mss.mss() as sct:
                        monitor = {"top": self.magic_hammer_locate[1], 
                                  "left": self.magic_hammer_locate[0],
                                  "width": 1, "height": 1}
                        screenshot = np.array(sct.grab(monitor))
                        
                    # Pikselin BGR değerini al
                    pixel_color = screenshot[0, 0, :3]  # BGR format
                    
                    # Hedef renk #AC3335 (BGR: 53, 51, 172) ile karşılaştır (toleranslı)
                    b_diff = abs(int(pixel_color[0]) - self.magic_hammer_target_color[0])
                    g_diff = abs(int(pixel_color[1]) - self.magic_hammer_target_color[1])
                    r_diff = abs(int(pixel_color[2]) - self.magic_hammer_target_color[2])
                    
                    # Renk yaklaşık olarak eşleşiyor mu?
                    if b_diff <= renk_toleransi and g_diff <= renk_toleransi and r_diff <= renk_toleransi:
                        # Son kullanımdan beri yeterli süre geçti mi?
                        current_time = time.time() * 1000  # milisaniye cinsinden şu anki zaman
                        if current_time - self.magic_hammer_last_used >= bekleme_suresi_ms:
                            hex_color = '#{:02X}{:02X}{:02X}'.format(pixel_color[2], pixel_color[1], pixel_color[0])
                            print(f"MagicHammer rengi tespit edildi! Piksel rengi: {hex_color}, Hedef renk: #AC3335")
                            
                            # Tuşa bas
                            keycode = self.keycodes.get(self.magic_hammer_shortcut[1], None)
                            if keycode:
                                print(f"MagicHammer tuşu basılıyor: {self.magic_hammer_shortcut}")
                                self.tusbas(keycode, 0.005)  # 5ms basılı tut
                                
                                # Son kullanım zamanını güncelle
                                self.magic_hammer_last_used = current_time
                                
                                print(f"MagicHammer kullanıldı. Sonraki kontrol için 5 saniye bekleniyor...")
            except Exception as e:
                print(f"MagicHammer kontrolünde hata: {e}")
                
            # Kontrol aralığı
            time.sleep(kontrol_suresi_saniye)
            
        print("MagicHammer kontrolü sonlandırıldı.")

    def auto_heal_buff_start(self):
        """Gelişmiş Auto Heal ve Buff sistemini başlatır."""
        # Heal tuşunu kontrol et
        if not self.auto_heal_buff_widget.heal_key:
            # Mevcut heal tuşunu kullan
            if self.heal_shortcut:
                self.auto_heal_buff_widget.heal_key = self.heal_shortcut[1]
            else:
                self.information_signal.emit("Lütfen önce bir iyileştirme tuşu belirleyin.")
                return
        
        # İyileştirme işlemini başlat
        self.auto_heal_buff_widget.start_working()
        self.auto_heal_buff_start_button.setStyleSheet("background-color: #387040; color: #FFFFFF; font-weight: bold;")
        self.auto_heal_buff_stop_button.setStyleSheet("background-color: #702F2F; color: #FFFFFF;")
        self.information_signal.emit("Gelişmiş Auto Heal ve Buff sistemi başlatıldı.")

    def auto_heal_buff_stop(self):
        """Gelişmiş Auto Heal ve Buff sistemini durdurur."""
        self.auto_heal_buff_widget.stop_working()
        self.auto_heal_buff_start_button.setStyleSheet("background-color: #387040; color: #FFFFFF;")
        self.auto_heal_buff_stop_button.setStyleSheet("background-color: #702F2F; color: #FFFFFF; font-weight: bold;")
        self.information_signal.emit("Gelişmiş Auto Heal ve Buff sistemi durduruldu.")

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    if app.exec_() == 0:
        os._exit(0)
