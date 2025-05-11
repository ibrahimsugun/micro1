# Fare Kaydedici (Mouse Recorder) v0.3

Fare Kaydedici, ekranda fare tıklamalarını kaydedip sonrasında bu tıklamaları otomatik olarak tekrarlayan basit bir otomasyon uygulamasıdır.

## Özellikler

- Tüm fare tıklamalarını (sağ ve sol) ve tıklamalar arasındaki gecikmeleri kaydetme
- Kaydedilen noktalarda otomatik sağ/sol tıklama yapma
- Orijinal tıklama gecikmelerini taklit etme veya sabit gecikme kullanma
- Tek seferlik veya sürekli tekrarlama seçeneği
- Kayıtları profil olarak saklama ve yükleme
- Klavye kısayolları ile kolay kullanım
- Windows sistemlerde win32api ile gerçek fare tıklaması

## Teknik Detaylar

Program PyQt5 kullanarak geliştirilmiş bir arayüze sahiptir ve şu özellikler ile çalışır:

- Klavye izleme için `keyboard` kütüphanesi kullanılır
- Fare tıklamaları için `win32api` kullanılır
- Ekran koordinatları ile çalışmak için `pyautogui` kullanılır
- Çoklu thread desteği sayesinde arayüz kilitlenmeden arka planda işlemler yapılabilir
- Profil verileri INI formatında saklanır (settings.ini)

## Kullanım

1. Uygulamayı başlatın
2. "Tıklamaları Kaydet" butonuna tıklayarak kayda başlayın
3. İstediğiniz yerlere sağ veya sol tıklamalar yapın
4. "B" tuşuna basarak veya "Kaydı Durdur" butonuna tıklayarak kaydı durdurun
5. "Profil Adı" kısmına bir isim girin ve "Kaydet" butonuna tıklayarak kaydınızı saklayın
6. "Oynat" butonuna tıklayarak kaydedilmiş tıklamaları oynatın
7. Durdurmak için "Durdur" butonunu kullanın veya "ESC" tuşuna basın

## Profil Yönetimi

- **Kaydet**: Mevcut tıklama verilerini belirtilen profil adıyla kaydeder
- **Yükle**: Belirtilen profil adından tıklama verilerini yükler
- **Sıfırla**: Mevcut tıklama verilerini temizler

Tüm profiller `settings.ini` dosyasına kaydedilir ve program yeniden başlatıldığında son kullanılan profil otomatik olarak yüklenir.

## Oynatma Seçenekleri

- **Sürekli tekrarla**: İşaretlendiğinde, tıklama serisi sürekli tekrarlanır
- **Kaydedilen tıklama gecikmelerini kullan**: İşaretlendiğinde, orijinal tıklama gecikmeleri kullanılır (gerçekçi zamanlama)

## Klavye Kısayolları

- **B** tuşu: Kaydı durdur
- **C** tuşu: Oynat
- **ESC** tuşu: Durdur

## Gereksinimler

- Python 3.6 veya üzeri
- PyQt5
- pyautogui
- keyboard
- pywin32
- configparser

## Kurulum

Gerekli kütüphaneleri yüklemek için:

```
pip install -r requirements.txt
```

Veya kütüphaneleri tek tek yüklemek için:

```
pip install PyQt5 pyautogui keyboard pywin32 configparser
```

Programı çalıştırmak için:

```
python point_recorder.py
```

## Notlar

- Program çalışırken kaydedilen tıklamalar arayüzde gösterilir
- Oynatma durdurulana kadar veya program kapatılana kadar devam eder
- Otomatik tıklama yapıldığı için oynatma sırasında fareyi kullanmamaya dikkat edin
- Tıklamalar arasındaki gerçek gecikmeler kaydedilir, böylece insansı hareketler taklit edilebilir

## Güvenlik

- `pyautogui.FAILSAFE = False` ile güvenlik önlemesi devre dışı bırakılmıştır, bu nedenle oynatma sırasında dikkatli olun
- Program sadece geliştirme ve test amaçlıdır, kötüye kullanımdan kullanıcı sorumludur

## Lisans

Bu yazılım açık kaynak olarak MIT lisansı altında dağıtılmaktadır.

## Geliştirici

Fare Kaydedici ekibi tarafından geliştirilmiştir. 