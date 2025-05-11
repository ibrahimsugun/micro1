# Ekran Tarayıcı

Bu program, ekranda belirli bir görüntüyü arar ve bulduğunda veya bulamadığında belirtilen tuşlara basar. Modüler yapı sayesinde birden fazla farklı işlem tanımlanabilir.

## Özellikler

- Ekranda belirli bir görüntüyü arama
- Görüntü bulunduğunda belirtilen tuşa basma
- Görüntü bulunamadığında belirtilen zaman aralığında başka bir tuşa basma
- Birden fazla işlem tanımlama ve yönetme
- Tüm işlemlerin veritabanında saklanması
- İşlem geçmişinin loglanması

## Gereksinimler

- Python 3.6 veya üzeri
- OpenCV
- NumPy
- Pillow
- PyAutoGUI
- Keyboard

## Kurulum

1. Projeyi klonlayın veya indirin
2. Gerekli bağımlılıkları yükleyin:
   ```
   pip install -r requirements.txt
   ```
3. Programı çalıştırın:
   ```
   python main.py
   ```

## Kullanım

1. Ana menüden "Yeni tarama başlat" seçeneğini seçin
2. Listeden bir işlem seçin
3. Ekranda tarama yapılacak bölgeyi fare ile seçin
4. Taramayı durdurmak için 'q' tuşuna basın

## Yeni İşlem Ekleme

1. Ana menüden "Yeni işlem ekle" seçeneğini seçin
2. İstenilen bilgileri girin:
   - İşlem adı
   - Aranacak görüntünün yolu (varsayılan: images/test.gif)
   - Görüntü bulunduğunda basılacak tuş
   - Görüntü bulunamadığında basılacak tuş (isteğe bağlı)
   - Kontrol aralığı (saniye)
   - Eşleşme eşiği (0.0-1.0 arası)

## Modüller

- **config.py**: Konfigürasyon ayarları
- **database.py**: Veritabanı işlemleri
- **image_processor.py**: Görüntü işleme
- **keyboard_controller.py**: Klavye kontrolü
- **scanner.py**: Tarama işlemleri
- **ui.py**: Kullanıcı arayüzü

## Notlar

- Program, "images/test.gif" dosyasını varsayılan şablon olarak kullanmaktadır.
- Tüm işlem bilgileri "data/screen_scanner.db" veritabanında saklanmaktadır.
- İşlem geçmişi logları da veritabanında tutulmaktadır. 