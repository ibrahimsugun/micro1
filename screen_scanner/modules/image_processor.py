"""
Görüntü İşleme Modülü
Bu modül, ekran görüntüsü alma ve görüntü eşleştirme işlevlerini yönetir.

Özellikleri:
- Belirli ekran bölgelerinin yakalanması
- Şablon eşleştirme algoritması ile görüntü arama
- Görsel geri bildirim için dikdörtgen çizim fonksiyonları
- Görüntüleri gösterme ve pencere yönetimi
- Hata yönetimi ve geniş istisna işleme

Bu modül, Screen Scanner uygulamasının temel görüntü işleme yeteneklerini sağlar
ve hem tam ekran hem de belirli bölgelerde görüntü eşleştirme yapabilir.
"""
import cv2
import numpy as np
import time
from PIL import ImageGrab
import os

def get_screen_region(x1, y1, x2, y2):
    """
    Belirtilen koordinatlardaki ekran bölgesinin görüntüsünü alır.
    
    Ekran üzerinde belirlenen dikdörtgen bölgenin piksel verilerini yakalar
    ve OpenCV ile işlemeye uygun formata dönüştürür. Bu fonksiyon,
    performans optimizasyonu için tüm ekran yerine belirli bir bölgede
    arama yapmak istendiğinde kullanılır.
    
    Args:
        x1, y1: Sol üst köşe koordinatları
        x2, y2: Sağ alt köşe koordinatları
        
    Returns:
        Belirtilen bölgenin OpenCV formatında görüntüsü (numpy array) veya
        hata durumunda None
    
    Raises:
        Exception: Ekran görüntüsü alma sırasında oluşabilecek hatalar
    """
    try:
        # PIL ile ekran bölgesini yakala
        screen = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        # PIL görüntüsünü OpenCV formatına dönüştür (RGB->BGR)
        return cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"Ekran bölgesi alınırken hata oluştu: {e}")
        return None

def find_image_on_screen(template_path, region=None, threshold=0.8):
    """
    Belirtilen şablon görüntüyü ekranda arar.
    
    Bu fonksiyon, template matching (şablon eşleştirme) algoritması kullanarak
    belirtilen görüntünün ekranda veya belirli bir ekran bölgesinde olup
    olmadığını kontrol eder. Eşleşmenin doğruluğu threshold parametresi ile
    belirlenir (0-1 arasında, 1'e yaklaştıkça daha kesin eşleşme gerekir).
    
    Args:
        template_path: Şablon görüntünün dosya yolu (aranacak resim)
        region: Arama yapılacak bölge (x1, y1, x2, y2) veya None (tüm ekran)
        threshold: Eşleşme eşiği (0.0-1.0), yüksek değerler daha kesin eşleşme gerektirir
        
    Returns:
        Eşleşme bulunursa (x, y, w, h) şeklinde koordinatlar ve boyutlar
        bulunamazsa None döner
        
    Not:
        Dönüş değerindeki (x, y) koordinatları şablonun sol üst köşesinin konumudur
        w ve h ise şablon görüntünün genişlik ve yüksekliğidir
    """
    try:
        # Şablon görüntüyü kontrol et - dosya var mı?
        if not os.path.exists(template_path):
            print(f"Hata: {template_path} dosyası bulunamadı!")
            return None
            
        # İstenilen bölge veya tüm ekranın görüntüsünü al
        if region:
            # Belirli bir bölge belirtilmişse sadece o alanı tara
            screen = get_screen_region(*region)
        else:
            # Belirli bir bölge belirtilmemişse tüm ekranı tara
            screen = np.array(ImageGrab.grab())
            screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)
            
        if screen is None:
            return None

        # Şablon görüntüyü oku
        template = cv2.imread(template_path)
        if template is None:
            print(f"Hata: {template_path} dosyası okunamadı!")
            return None

        # OpenCV'nin şablon eşleştirme algoritmasını uygula
        # TM_CCOEFF_NORMED yöntemi, normalize edilmiş çapraz korelasyon katsayısını kullanır
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        
        # Minimum ve maksimum değerleri ve konumlarını bul
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # max_val, şablonun ekrandaki en iyi eşleşme skoru (0-1 arası)
        # Eşik değerinden yüksek bir eşleşme var mı kontrol et
        if max_val >= threshold:
            # Şablonun boyutlarını al ve sonucu döndür
            w, h = template.shape[1], template.shape[0]
            return (max_loc[0], max_loc[1], w, h)
            
        # Eşik değerinin altında eşleşme yoksa None döndür
        return None
    except Exception as e:
        print(f"Görüntü eşleştirme sırasında hata oluştu: {e}")
        return None

def draw_rectangle(image, x, y, w, h, color=(0, 255, 0), thickness=2):
    """
    Görüntü üzerine dikdörtgen çizer.
    
    Bu fonksiyon, eşleşen görüntülerin konumunu görsel olarak vurgulamak için
    kullanılır. Özellikle hata ayıklama ve kullanıcı geri bildirimi için
    faydalıdır.
    
    Args:
        image: Üzerine çizim yapılacak görüntü (numpy array)
        x, y: Sol üst köşe koordinatları
        w, h: Genişlik ve yükseklik
        color: BGR renk değeri, varsayılan: yeşil (0, 255, 0)
        thickness: Çizgi kalınlığı, piksel cinsinden
    
    Returns:
        Dikdörtgen çizilmiş görüntü (orijinal değiştirilmez)
        
    Not:
        OpenCV, renk formatı olarak BGR kullanır (RGB değil)
    """
    try:
        # Orijinal görüntüyü korumak için kopyasını oluştur
        result = image.copy()
        # Dikdörtgeni çiz
        cv2.rectangle(result, (x, y), (x + w, y + h), color, thickness)
        return result
    except Exception as e:
        print(f"Dikdörtgen çizme hatası: {e}")
        # Hata durumunda orijinal görüntüyü döndür
        return image

def display_image(window_name, image):
    """
    Görüntüyü bir pencerede gösterir.
    
    Bu fonksiyon, işlenen görüntülerin kullanıcıya gösterilmesi için kullanılır.
    Özellikle hata ayıklama ve gerçek zamanlı geri bildirim için faydalıdır.
    
    Args:
        window_name: Pencere adı (benzersiz tanımlayıcı)
        image: Gösterilecek görüntü (numpy array)
        
    Not:
        Bu fonksiyon cv2.waitKey(1) çağrısı yapar, bu da pencereyi güncellemek 
        ve olayları işlemek için gereklidir. Pencereyi kapatmak için
        close_all_windows() fonksiyonu kullanılmalıdır.
    """
    try:
        # Görüntüyü belirtilen pencere adıyla göster
        cv2.imshow(window_name, image)
        # 1ms bekle (pencere güncelleme ve olay işleme için)
        cv2.waitKey(1)
    except Exception as e:
        print(f"Görüntü gösterme hatası: {e}")

def close_all_windows():
    """
    Tüm OpenCV pencerelerini kapatır.
    
    Bu fonksiyon, uygulama kapanırken veya görüntü gösterimi artık 
    gerekmediğinde tüm açık pencereleri temizlemek için kullanılır.
    Sistem kaynaklarının düzgün şekilde serbest bırakılmasını sağlar.
    """
    cv2.destroyAllWindows() 