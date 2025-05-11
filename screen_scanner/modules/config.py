"""
Konfigürasyon Modülü
Bu modül, program genelinde kullanılan konfigürasyon değişkenlerini içerir.
Programın ayarlanabilir parametreleri burada tanımlanır.
"""
import os

# Veritabanı ayarları
DATABASE_PATH = os.path.join("data", "screen_scanner.db")

# Görüntü arama ayarları
DEFAULT_TEMPLATE_PATH = os.path.join("images", "test.gif")
DEFAULT_KEY_TO_PRESS = "e"
DEFAULT_KEY_WHEN_NOT_FOUND = "6"
DEFAULT_CHECK_INTERVAL = 5  # saniye
DEFAULT_THRESHOLD = 0.8  # Eşleşme eşiği (0.0 - 1.0)

# Genel program ayarları
PROGRAM_NAME = "Ekran Tarayıcı"
VERSION = "1.0.0"

# Loglama ayarları
ENABLE_LOGS = True
LOG_FILE = os.path.join("data", "scan_log.txt") 