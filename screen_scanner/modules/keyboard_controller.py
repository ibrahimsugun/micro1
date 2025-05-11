"""
Klavye Kontrol Modülü
Bu modül, klavye tuşlarını simüle etmek ve klavye olaylarını dinlemek için fonksiyonlar içerir.
"""
import keyboard
import time
from modules.database import log_action

def press_key(key, task_id=None):
    """
    Belirtilen tuşa basma işlemi yapar.
    
    Args:
        key: Basılacak tuş
        task_id: İşlem ID'si (loglama için)
    
    Returns:
        Başarılı ise True, değilse False
    """
    try:
        keyboard.press_and_release(key)
        
        # Loglama
        if task_id is not None:
            log_action(task_id, "key_press", f"Tuşa basıldı: {key}")
            
        return True
    except Exception as e:
        print(f"Tuşa basma hatası: {e}")
        return False

def is_key_pressed(key):
    """
    Belirtilen tuşun basılı olup olmadığını kontrol eder.
    
    Args:
        key: Kontrol edilecek tuş
        
    Returns:
        Tuş basılı ise True, değilse False
    """
    try:
        return keyboard.is_pressed(key)
    except Exception as e:
        print(f"Tuş kontrol hatası: {e}")
        return False

def wait_for_key_press(key, timeout=None):
    """
    Belirtilen tuşa basılmasını bekler.
    
    Args:
        key: Beklenen tuş
        timeout: Zaman aşımı süresi (saniye)
        
    Returns:
        Tuşa basıldıysa True, zaman aşımına uğradıysa False
    """
    try:
        start_time = time.time()
        
        while True:
            if keyboard.is_pressed(key):
                return True
                
            # Zaman aşımı kontrolü
            if timeout is not None and time.time() - start_time > timeout:
                return False
                
            # CPU kullanımını azaltmak için kısa bekleme
            time.sleep(0.01)
    except Exception as e:
        print(f"Tuş bekleme hatası: {e}")
        return False 