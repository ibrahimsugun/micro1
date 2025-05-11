"""
Tarama Modülü (Scanner Module)

Bu modül, Screen Scanner uygulamasının temel işlevselliğini sağlayan tarama 
mekanizmasını içermektedir. Belirtilen ekran bölgesinde hedef görüntüyü arar
ve bulma/bulamama durumlarına göre tanımlanmış klavye tuşlarına otomasyon ile basar.

Özellikler:
- Dinamik görüntü tanıma ve eşleştirme
- Otomatik klavye kontrolü
- Görsel geri bildirim (ekranda gösterme)
- Kapsamlı log ve kayıt tutma
"""
import time
import cv2
from modules.image_processor import find_image_on_screen, close_all_windows
from modules.keyboard_controller import press_key, is_key_pressed
from modules.ui import show_detection_window, print_task_info
from modules.database import log_action

def run_scanner(task, region):
    """
    Ana tarama döngüsünü çalıştırarak belirlenen bölgede belirtilen görüntüyü arar
    ve ilgili durumlarda belirtilen klavye tuşlarına basar.
    
    İşleyiş:
    1. Ekranın belirtilen bölgesini sürekli tarar
    2. Görüntü bulunduğunda 'key_to_press' tuşuna basar
    3. Görüntü bulunamadığında (ve tanımlanmışsa) 'key_when_not_found' tuşuna basar
    4. Tüm işlemleri veritabanına kaydeder
    5. Kullanıcı 'q' tuşuna basana kadar devam eder
    
    Args:
        task (dict): Tarama işlemi ayarlarını içeren sözlük. Şu anahtarları içermelidir:
            - id: Görev kimliği
            - name: Görev adı
            - image_path: Aranacak görüntünün dosya yolu
            - key_to_press: Görüntü bulunduğunda basılacak tuş
            - key_when_not_found: Görüntü bulunamadığında basılacak tuş (None olabilir)
            - check_interval: Kontrol sıklığı (saniye cinsinden)
            - threshold: Eşleşme eşiği (0.1-1.0 arası)
            
        region (tuple): (x1, y1, x2, y2) şeklinde tarama yapılacak ekran bölgesinin koordinatları
            - x1, y1: Sol üst köşe koordinatları
            - x2, y2: Sağ alt köşe koordinatları
    
    Returns:
        None: Fonksiyon doğrudan çıktı döndürmez. Etkileri ekrana yazdırma, tuşlara basma ve 
              log kayıtlarını yazma şeklindedir.
    """
    # Görev parametrelerini ayıklama
    task_id = task['id']
    template_path = task['image_path']
    key_to_press = task['key_to_press']
    key_when_not_found = task['key_when_not_found']
    check_interval = task['check_interval']
    threshold = task['threshold']
    
    # Göreve ve tarama bölgesine dair bilgileri göster
    print_task_info(task)
    print(f"Seçilen bölge: {region}")
    print("\nTarama başlatıldı. Çıkmak için 'q' tuşuna basın...")
    
    # Son kontrol zamanını kaydet ve tarama başlangıcını logla
    last_check_time = time.time()
    log_action(task_id, "scanner_start", f"Bölge: {region}")
    
    try:
        # Ana döngü - kullanıcı çıkış yapana kadar devam eder
        while True:
            # Kullanıcı çıkış tuşuna bastı mı kontrolü
            if is_key_pressed('q'):
                print("Tarama sonlandırılıyor...")
                log_action(task_id, "scanner_stop", "Kullanıcı tarafından durduruldu")
                break
            
            # Belirtilen bölgede görüntü arama işlemi
            # result = None veya (x, y, w, h) şeklinde eşleşme bulunduğunda konum ve boyut bilgisi
            result = find_image_on_screen(template_path, region, threshold)
            current_time = time.time()
            
            # Tarama sonucunu ekranda görselleştir
            show_detection_window(region, result, f"Tarama - {task['name']}")
            
            # Görüntü bulunma durumunu kontrol et ve ilgili aksiyonu al
            if result:
                # Görüntü bulundu - koordinatları al ve tanımlanan tuşa bas
                x, y, w, h = result
                press_key(key_to_press, task_id)
                # Olayı logla ve ekrana bilgi yazdır
                log_action(task_id, "image_found", f"Konum: ({x}, {y})")
                print(f"Görüntü bulundu! {key_to_press} tuşuna basıldı.")
                time.sleep(0.5)  # Sürekli basmaması için kısa bir bekleme
            elif key_when_not_found and current_time - last_check_time >= check_interval:
                # Belirtilen süre geçtiyse ve görüntü bulunamadıysa belirtilen tuşa bas
                press_key(key_when_not_found, task_id)
                # Olayı logla ve ekrana bilgi yazdır
                log_action(task_id, "image_not_found", f"Kontrol süresi: {check_interval}s")
                print(f"Görüntü bulunamadı! {key_when_not_found} tuşuna basıldı.")
                last_check_time = current_time
            
            # CPU kullanımını azaltmak için kısa bekleme
            time.sleep(0.01)
            
            # OpenCV pencere kontrolü - 'q' tuşuna basıldıysa döngüden çık
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except Exception as e:
        # Hata durumunda bilgilendirme ve loglama
        error_msg = f"Tarama sırasında hata oluştu: {e}"
        print(error_msg)
        log_action(task_id, "error", error_msg)
    finally:
        # Her durumda pencereyi kapat ve tarama bitişini logla
        close_all_windows()
        log_action(task_id, "scanner_end", "Tarama tamamlandı") 