import cv2
import numpy as np
import pyautogui
import time
from PIL import ImageGrab
import keyboard

# Sabit değişkenler
TEMPLATE_PATH = "./images/test.gif"
KEY_TO_PRESS = "e"
KEY_WHEN_NOT_FOUND = "6"
CHECK_INTERVAL = 5 # saniye
eeeeeeeeeeeeeeeeee6
def get_screen_region(x1, y1, x2, y2):
    screen = ImageGrab.grab(bbox=(x1, y1, x2, y2))
    return cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)

# Görüntü eşleştirme fonksiyonu
def find_image_on_screen(template_path, region=None, threshold=0.8):
    if region:
        screen = get_screen_region(*region)
    else:
        screen = np.array(ImageGrab.grab())
        screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)

    template = cv2.imread(template_path)
    if template is None:
        print(f"Hata: {template_path} dosyası bulunamadı!")
        return None

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= threshold:
        w, h = template.shape[1], template.shape[0]
        return (max_loc[0], max_loc[1], w, h)
    return None

def main():
    print("Program başlatıldı.")
    print(f"Aranacak dosya: {TEMPLATE_PATH}")
    print(f"Görüntü bulunduğunda basılacak tuş: {KEY_TO_PRESS}")
    print(f"Görüntü bulunamadığında her {CHECK_INTERVAL} saniyede bir basılacak tuş: {KEY_WHEN_NOT_FOUND}")
    print("\nEkran bölgesini seçmek için:")
    print("1. Sol üst köşeyi tıklayın ve basılı tutun")
    print("2. Sağ alt köşeye sürükleyin")
    print("3. Bırakın")
    print("\nProgram başladıktan sonra çıkmak için 'q' tuşuna basın.")

    # İlk tıklama noktasını al
    print("\nLütfen bölgeyi seçin...")
    x1, y1 = pyautogui.position()
    print(f"Başlangıç noktası: ({x1}, {y1})")

    # Fare tıklamasını bekle ve sürükleme sırasında dikdörtgeni çiz
    while not keyboard.is_pressed('space'):
        x2, y2 = pyautogui.position()
        # Ekran görüntüsü al
        screen = np.array(ImageGrab.grab())
        screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)

        # Dikdörtgeni çiz
        cv2.rectangle(screen, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Ekranı göster
        cv2.imshow('Selection', screen)
        cv2.waitKey(1)

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
    region = (left, top, right, bottom)

    print(f"Seçilen bölge: {region}")
    print("\nProgram çalışıyor...")

    last_check_time = time.time()

    # Ana döngü
    while True:
        if keyboard.is_pressed('q'):
            print("Program sonlandırılıyor...")
            break

        # Ekran görüntüsü al ve işle
        screen = get_screen_region(*region)

        # Görüntü eşleştirme
        result = find_image_on_screen(TEMPLATE_PATH, region)

        current_time = time.time()

        # Ekranda göster
        if result:
            x, y, w, h = result
            # Bulunan bölgeyi yeşil dikdörtgen içine al
            cv2.rectangle(screen, (x, y), (x + w, y + h), (0, 255, 0), 2)
            # Tuşa bas
            keyboard.press_and_release(KEY_TO_PRESS)
            print(f"Görüntü bulundu! {KEY_TO_PRESS} tuşuna basıldı.")
            time.sleep(0.5) # Sürekli basmaması için kısa bir bekleme
        elif current_time - last_check_time >= CHECK_INTERVAL:
            # Belirtilen süre geçtiyse ve görüntü bulunamadıysa 6 tuşuna bas
            keyboard.press_and_release(KEY_WHEN_NOT_FOUND)
            print(f"Görüntü bulunamadı! {KEY_WHEN_NOT_FOUND} tuşuna basıldı.")
            last_check_time = current_time

        cv2.imshow('Detection', screen)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()