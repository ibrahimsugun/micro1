import json
import os
import pyautogui
import random
import time
import numpy as np
from PyQt5.QtWidgets import QApplication, QComboBox, QWidget, QPushButton, QTabWidget, QLabel, QLineEdit, QSlider, QVBoxLayout, QHBoxLayout, QCheckBox, QMessageBox, QStackedWidget
from PyQt5.QtCore import Qt, pyqtSignal
import threading
from pynput.keyboard import Listener, Key
import mss
import string
from interception import *
import ctypes
import cv2
import configparser

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
        
        try:
            self.driver = interception()
            for i in range(MAX_DEVICES):
                if interception.is_keyboard(i):
                    self.keyboard = i
                    print(f"Keyboard found: {i}")
                    break
            if self.keyboard == None:
                print("Keyboard not found.")
        except:
            pass

        # Variables from deneme.py
        self.heal_locate = []
        self.heal_min = 15
        self.heal_shortcut = ''
        self.mana_locate = []
        self.mana_min = 15
        self.mana_shortcut = ''
        self.oto_heal = False
        self.oto_mana = False
        self.oto_heal_mana_ms = 100
        
        # Variables from yeni.py
        self.Makro_keys = ''
        self.Makro_ms = 1
        self.Makro_use_continuously_bool = False
        self.Makro_using = False
        self.Makro_use = True
        
        self.target_job = 0
        self.working = False
        
        self.start_key_listener()
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
        self.setGeometry(100, 100, 400, 600)

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

        # Checkboxes
        self.oto_heal_checkbox = QCheckBox("Oto-HP")
        self.oto_heal_checkbox.stateChanged.connect(self.oto_heal_func)
        self.oto_heal_checkbox.setToolTip("HP barı belirlenen seviyenin altına düştüğünde otomatik pot kullanır.")
        
        self.oto_mana_checkbox = QCheckBox("Oto-MP")
        self.oto_mana_checkbox.stateChanged.connect(self.oto_mana_func)
        self.oto_mana_checkbox.setToolTip("MP barı belirlenen seviyenin altına düştüğünde otomatik pot kullanır.")

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

        # Makro Controls
        self.Makro_keys_label = QLabel("Makro:")
        self.Makro_keys_input = QLineEdit()
        self.Makro_keys_input.setText(self.Makro_keys)
        self.Makro_keys_input.setToolTip("Makroda kullanılacak tuşları girin. Örnek: 123F1F2 (Z tuşunu eklemeyin, otomatik eklenecek)")
        self.Makro_keys_input.textChanged.connect(self.Makro_keys_func)
        
        self.Makro_ms_label = QLabel("Hız: 0001")
        self.Makro_ms_input = QSlider(Qt.Horizontal)
        self.Makro_ms_input.setMinimum(1)
        self.Makro_ms_input.setMaximum(1000)
        self.Makro_ms_input.valueChanged.connect(self.Makro_ms_changed)
        self.Makro_ms_input.setToolTip("Makronun çalışma hızını belirler. 1-1000 ms arasında ayarlanabilir.")
        
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

        self.setup_layout()

    def setup_layout(self):
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
        
        # Target Section
        target_group = QVBoxLayout()
        target_group.addWidget(self.take_target_locate)
        
        # Makro Section
        makro_group = QVBoxLayout()
        
        # Makro Input Row
        makro_input_row = QHBoxLayout()
        makro_input_row.addWidget(self.Makro_keys_label)
        makro_input_row.addWidget(self.Makro_keys_input)
        makro_group.addLayout(makro_input_row)
        
        # Makro Speed Row
        makro_speed_row = QHBoxLayout()
        makro_speed_row.addWidget(self.Makro_ms_label)
        makro_speed_row.addWidget(self.Makro_ms_input)
        makro_group.addLayout(makro_speed_row)
        
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
        main_layout.addLayout(target_group)
        main_layout.addLayout(makro_group)
        main_layout.addLayout(control_buttons)
        
        # Add contact information
        contact_label = QLabel()
        contact_label.setOpenExternalLinks(True)
        contact_label.setText("<a href='https://github.com/cgetiren/' style='color: white;'>iletişim: github/cgetiren</a>")
        main_layout.addWidget(contact_label)
        
        self.setLayout(main_layout)

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

    def Makro_keys_func(self):
        if not self.working:
            try:
                self.Makro_keys = [i for i in self.Makro_keys_input.text().upper()]
            except ValueError:
                self.Makro_keys_input = 'Bir hata oluştu'

    def Makro_ms_changed(self):
        try:
            self.Makro_ms = int(self.Makro_ms_input.value())
            self.Makro_ms_label.setText(f"Hız: {self.Makro_ms:04d}")
        except ValueError:
            self.Makro_ms = 100

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
        
        # Hedef durumu değiştiyse makro tuşlarını güncelle
        if has_target != self.last_target_state:
            print(f"Hedef durumu değişti: {'Var' if has_target else 'Yok'} (Kırmızı piksel sayısı: {red_pixel_count})")
            if has_target:
                # Hedef varsa Z tuşunu kaldır
                if 'Z' in self.Makro_keys:
                    self.Makro_keys.remove('Z')
            else:
                # Hedef yoksa Z tuşunu ekle
                if 'Z' not in self.Makro_keys:
                    self.Makro_keys.append('Z')
            
            # Makro tuşlarını güncelle
            self.Makro_keys_input.setText(''.join(self.Makro_keys))
        
        self.last_target_state = has_target
        return has_target

    def target_detection_helper(self):
        while self.working and self.target_detection:
            try:
                if len(self.target_locate) == 2:
                    self.take_screenshot((self.target_locate[0], self.target_locate[1], self.target_locate[0] + 1, self.target_locate[1] + 1))
                    rgb = self.screenshot[0, 0]
                    # Hedef çubuğu genellikle kırmızı renktedir
                    if rgb[2] > 200 and rgb[1] < 50 and rgb[0] < 50:  # Kırmızı renk kontrolü
                        self.last_target_state = True
                    else:
                        self.last_target_state = False
            except Exception as e:
                print(f"Hedef tespitinde hata: {e}")
            time.sleep(0.1)  # Her 100ms'de bir kontrol et

    def Makro(self):
        while (self.working and self.Makro_use and self.Makro_using):
            # Tuşları sırayla bas
            for i in self.Makro_keys:
                if not (self.working and self.Makro_use and self.Makro_using):
                    break
                self.tusbas(self.keycodes[i], 0.0001)
                time.sleep(self.Makro_ms/1000)
            
            # Hedef yoksa Z ve hemen ardından R tuşuna bas
            if len(self.target_locate) == 2 and not self.last_target_state:
                # Z ve R tuşlarını çok hızlı bas
                self.tusbas(self.keycodes['Z'], 0.0001)
                self.tusbas(self.keycodes['R'], 0.0001)
                time.sleep(self.Makro_ms/1000)
            
            # Sürekli kullanım seçili değilse döngüyü bitir
            if not self.Makro_use_continuously_bool:
                self.working = False
                self.start_stop_shortcut_buton.setStyleSheet("background-color: #702F2F; color: #FFFFFF;")
                break

    def heal_mana_helper(self):
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
        
        while self.working and (self.oto_heal or self.oto_mana):
            self.take_screenshot(region, target=0)
            
            if self.oto_heal:
                rgb = self.heal_and_mana_screenshot[self.heal_locate[1], self.heal_locate[0]]
                if rgb[0] <= self.heal_min and rgb[1] <= self.heal_min and rgb[2] <= self.heal_min:
                    tus = self.heal_shortcut[1]
                    if self.oto_heal_page != 'F Sayfası':
                        self.tusbas(self.keycodes[self.oto_heal_page], 0.09)
                    self.tusbas(self.keycodes[tus], 0.09)
                    
            if self.oto_mana:
                rgb = self.heal_and_mana_screenshot[self.mana_locate[1], self.mana_locate[0]]
                if rgb[0] <= self.mana_min and rgb[1] <= self.mana_min and rgb[2] <= self.mana_min:
                    tus = self.mana_shortcut[1]
                    if self.oto_mana_page != 'F Sayfası':
                        self.tusbas(self.keycodes[self.oto_mana_page], 0.09)
                    self.tusbas(self.keycodes[tus], 0.09)
                    
            time.sleep(0.1)

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

    def tusbas(self, key, gecikme):
        interception_press = key_stroke(key, interception_key_state.INTERCEPTION_KEY_DOWN.value, 0)
        self.driver.send(self.keyboard, interception_press)
        time.sleep(gecikme)  # 0.0001 saniye (0.1ms) gecikme
        interception_press.state = interception_key_state.INTERCEPTION_KEY_UP.value
        self.driver.send(self.keyboard, interception_press)

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
                    
            self.Makro_using = False
            self.Makro_keys_func()
            
            self.working = True
            if self.Makro_use:
                self.Makro_using = True
                self.target_detection = True
                threading.Thread(target=self.Makro, daemon=True).start()
                threading.Thread(target=self.target_detection_helper, daemon=True).start()
            if self.oto_heal or self.oto_mana:
                threading.Thread(target=self.heal_mana_helper, daemon=True).start()
            self.start_stop_shortcut_buton.setStyleSheet("background-color: #387040; color: #FFFFFF;")
        elif self.working == True:
            self.working = False
            self.target_detection = False
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
                if self.target_job == 1:
                    handle_target_job(self.take_heal_locate, self.heal_locate, "HP Kordinatları Alındı")
                elif self.target_job == 2:
                    handle_target_job(self.take_mana_locate, self.mana_locate, "MP Kordinatları Alındı")
                elif self.target_job == 6:  # Yeni hedef çubuğu konumu için
                    handle_target_job(self.take_target_locate, self.target_locate, "Hedef Çubuğu Konumu Alındı")
            elif self.target_job == 3:
                self.heal_shortcut = handle_shortcut(self.heal_shortcut, key, self.heal_shortcut_button, "HP")
            elif self.target_job == 4:
                self.mana_shortcut = handle_shortcut(self.mana_shortcut, key, self.mana_shortcut_button, "MP")
            elif self.target_job == 5:
                self.start_shortcut = handle_shortcut(self.start_shortcut, key, self.start_stop_shortcut_buton, "Başlat/Durdur")
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
            'makro_keys': ','.join(self.Makro_keys) if isinstance(self.Makro_keys, list) else self.Makro_keys,
            'makro_ms': str(self.Makro_ms),
            'start_shortcut': self.start_shortcut,
            'oto_mana_page': self.oto_mana_page,
            'oto_heal_page': self.oto_heal_page,
            'target_locate': ','.join(map(str, self.target_locate))
        }

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
            makro_keys = settings.get('makro_keys', '')
            self.Makro_keys = makro_keys.split(',') if ',' in makro_keys else list(makro_keys)
            self.Makro_ms = settings.getint('makro_ms', 1)
            self.start_shortcut = settings.get('start_shortcut', '')
            self.oto_mana_page = settings.get('oto_mana_page', 'F Sayfası')
            self.oto_heal_page = settings.get('oto_heal_page', 'F Sayfası')
            self.target_locate = [int(x) for x in settings.get('target_locate', '').split(',') if x]
            
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
        if len(self.Makro_keys) > 0:
            self.Makro_keys_input.setText(''.join(self.Makro_keys))
        if len(self.target_locate) > 0:  # Hedef çubuğu konumu kontrolü eklendi
            self.take_target_locate.setText("Hedef Çubuğu Konumu Alındı")
        self.Makro_ms_input.setValue(self.Makro_ms)
        self.Makro_use_continuously.setChecked(self.Makro_use_continuously_bool)
        self.Makro_use_checkbox.setChecked(self.Makro_use)
        self.Makro_ms_changed()

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
            
            # Makro ayarlarını sıfırla
            self.Makro_keys = ''
            self.Makro_ms = 1
            self.Makro_use_continuously_bool = False
            self.Makro_using = False
            self.Makro_use = True
            
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
            
            # Bilgi mesajı göster
            QMessageBox.information(self, "Bilgi", "Tüm ayarlar başarıyla sıfırlandı.")

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    if app.exec_() == 0:
        os._exit(0)
