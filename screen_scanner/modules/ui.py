"""
Kullanıcı Arayüzü Modülü
Bu modül, bölge seçimi ve ekran görüntüleme gibi kullanıcı arayüzü işlevlerini sağlar.
"""
import cv2
import numpy as np
import pyautogui
from modules.keyboard_controller import is_key_pressed, wait_for_key_press
from modules.image_processor import get_screen_region, display_image, draw_rectangle
import time

def select_screen_region(wait_key='space'):
    """
    Kullanıcının ekranda bir bölge seçmesini sağlar.
    
    Args:
        wait_key: Seçimi onaylamak için basılacak tuş
        
    Returns:
        (x1, y1, x2, y2) şeklinde seçilen bölge koordinatları
    """
    print("\nEkran bölgesini seçmek için:")
    print("1. Sol üst köşeyi tıklayın ve basılı tutun")
    print("2. Sağ alt köşeye sürükleyin")
    print(f"3. Bırakın ve '{wait_key}' tuşuna basın")
    
    # Kullanıcının fare tıklamasını bekle
    input("Hazır olduğunuzda Enter tuşuna basın...")
    
    # İlk tıklama noktasını al
    x1, y1 = pyautogui.position()
    print(f"Başlangıç noktası: ({x1}, {y1})")
    
    # Fare tıklamasını bekle ve sürükleme sırasında dikdörtgeni çiz
    while not is_key_pressed(wait_key):
        x2, y2 = pyautogui.position()
        
        # Ekran görüntüsü al
        screen = np.array(pyautogui.screenshot())
        screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)
        
        # Dikdörtgeni çiz
        cv2.rectangle(screen, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Ekranı göster
        display_image('Bölge Seçimi', screen)
        
        # CPU kullanımını azaltmak için kısa bekleme
        time.sleep(0.01)
    
    # Son noktayı al
    x2, y2 = pyautogui.position()
    print(f"Bitiş noktası: ({x2}, {y2})")
    
    # Seçim penceresini kapat
    cv2.destroyAllWindows()
    
    # Bölge koordinatlarını düzenle
    left = min(x1, x2)
    top = min(y1, y2)
    right = max(x1, x2)
    bottom = max(y1, y2)
    
    return (left, top, right, bottom)

def show_detection_window(region, detection_result=None, window_name='Tespit'):
    """
    Tespit sonucunu gösteren pencereyi görüntüler.
    
    Args:
        region: (x1, y1, x2, y2) şeklinde bölge koordinatları
        detection_result: (x, y, w, h) şeklinde tespit sonucu
        window_name: Pencere adı
    """
    # Belirtilen bölgenin ekran görüntüsünü al
    screen = get_screen_region(*region)
    
    if screen is None:
        return
    
    # Tespit varsa, dikdörtgen çiz
    if detection_result:
        x, y, w, h = detection_result
        screen = draw_rectangle(screen, x, y, w, h, (0, 255, 0), 2)
    
    # Ekranı göster
    display_image(window_name, screen)

def print_task_info(task):
    """
    İşlem bilgilerini ekrana yazdırır.
    
    Args:
        task: İşlem bilgilerini içeren sözlük
    """
    print("\n=== İşlem Bilgileri ===")
    print(f"İşlem Adı: {task['name']}")
    print(f"Görüntü Yolu: {task['image_path']}")
    print(f"Görüntü Bulunduğunda: {task['key_to_press']} tuşuna basılacak")
    print(f"Görüntü Bulunamadığında: Her {task['check_interval']} saniyede bir {task['key_when_not_found']} tuşuna basılacak")
    print(f"Eşleşme Eşiği: {task['threshold']}")
    print("=====================\n")

def print_welcome_message():
    """Karşılama mesajını yazdırır."""
    from modules.config import PROGRAM_NAME, VERSION
    
    print("="*50)
    print(f"{PROGRAM_NAME} v{VERSION}")
    print("="*50)
    print("Ekranınızda belirli bir görüntüyü arar ve bulduğunda belirlediğiniz tuşa basar.")
    print("Programı sonlandırmak için 'q' tuşuna basın.")
    print("="*50)

def display_menu():
    """Ana menüyü gösterir ve kullanıcı seçimini döndürür."""
    print("\n=== MENÜ ===")
    print("1. Yeni tarama başlat")
    print("2. İşlem listesini göster")
    print("3. Yeni işlem ekle")
    print("4. İşlem düzenle")
    print("5. İşlem sil")
    print("0. Çıkış")
    
    choice = input("\nSeçiminiz: ")
    return choice

def get_task_selection(tasks):
    """
    Kullanıcıdan bir işlem seçmesini ister.
    
    Args:
        tasks: İşlemler listesi
        
    Returns:
        Seçilen işlemin ID'si veya iptal için None
    """
    if not tasks:
        print("Hiç işlem bulunmuyor.")
        return None
    
    print("\n=== İşlemler ===")
    for i, task in enumerate(tasks):
        print(f"{i+1}. {task['name']} ({task['image_path']})")
    
    try:
        choice = int(input("\nSeçiminiz (0: İptal): "))
        if choice == 0:
            return None
        elif 1 <= choice <= len(tasks):
            return tasks[choice-1]['id']
        else:
            print("Geçersiz seçim!")
            return None
    except ValueError:
        print("Lütfen bir sayı girin!")
        return None

def get_new_task_info():
    """
    Yeni işlem için kullanıcıdan bilgi alır.
    
    Returns:
        İşlem bilgilerini içeren sözlük veya iptal için None
    """
    print("\n=== Yeni İşlem Ekleme ===")
    
    name = input("İşlem Adı: ")
    if not name:
        print("İşlem iptal edildi.")
        return None
    
    image_path = input("Görüntü Yolu (boş bırakılırsa varsayılan kullanılır): ")
    if not image_path:
        image_path = "images/test.gif"
    
    key_to_press = input("Görüntü Bulunduğunda Basılacak Tuş: ")
    if not key_to_press:
        print("İşlem iptal edildi.")
        return None
    
    key_when_not_found = input("Görüntü Bulunamadığında Basılacak Tuş (boş bırakılabilir): ")
    
    try:
        check_interval = input("Kontrol Aralığı (saniye, boş bırakılırsa varsayılan kullanılır): ")
        check_interval = int(check_interval) if check_interval else None
    except ValueError:
        print("Geçersiz değer, varsayılan kullanılacak.")
        check_interval = None
    
    try:
        threshold = input("Eşleşme Eşiği (0.0-1.0, boş bırakılırsa varsayılan kullanılır): ")
        threshold = float(threshold) if threshold else None
        if threshold is not None and (threshold < 0 or threshold > 1):
            print("Eşik değeri 0.0 ile 1.0 arasında olmalıdır, varsayılan kullanılacak.")
            threshold = None
    except ValueError:
        print("Geçersiz değer, varsayılan kullanılacak.")
        threshold = None
    
    return {
        'name': name,
        'image_path': image_path,
        'key_to_press': key_to_press,
        'key_when_not_found': key_when_not_found,
        'check_interval': check_interval,
        'threshold': threshold
    } 