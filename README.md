# Knight Online Party İyileştirme Makrosu

Bu makro programı, Knight Online oyununda parti üyelerinin can barlarını otomatik olarak izleyerek, belirlenen eşik değerinin altına düşen üyeleri otomatik olarak iyileştirebilir. Ayrıca, önceden tanımlanmış koordinatlarda otomatik tıklamalar gerçekleştirebilir.

## Özellikler

- **Parti Üyelerinin Can Barlarını İzleme**: Ekranın sağ kısmında bulunan parti can barlarını sürekli kontrol eder
- **Otomatik İyileştirme**: Canı belirlenen eşik değerinin altına düşen üyeleri otomatik olarak iyileştirir
- **Çoklu İş Parçacığı**: Tüm işlemler paralel ve sistem kaynaklarını yormayacak şekilde çalışır
- **Özelleştirilebilir İyileştirme Eşiği**: Kullanıcı can eşik değerini (örn %40) belirleyebilir
- **Tıklama Koordinatları**: Tiklamalar.txt dosyasından okunan koordinatlarda otomatik tıklamalar yapabilir

## Gereksinimler

Programı çalıştırmak için aşağıdaki paketlere ihtiyacınız vardır:

```
pip install pyautogui PyQt5 pynput mss numpy opencv-python keyboard pillow
```

## Kurulum ve Çalıştırma

1. Bu depoyu bilgisayarınıza indirin
2. Gerekli paketleri yükleyin
3. Python ile party_heal_macro.py dosyasını çalıştırın:

```
python party_heal_macro.py
```

## Kullanım Talimatları

1. Programı çalıştırın
2. "Parti Bölgesini Seç" butonuna tıklayın
   - Sol üst köşe için imlecinizi konumlandırın ve SPACE tuşuna basın
   - Sağ alt köşe için imlecinizi konumlandırın ve SPACE tuşuna basın
3. "İyileştirme Konumunu Seç" butonuna tıklayın
   - İyileştirme butonunun olduğu konuma imlecinizi getirin ve SPACE tuşuna basın
4. İyileştirme eşiğini (%) ayarlayın
5. İyileştirme bekleme süresini (ms) ayarlayın
6. "Başlat" butonuna tıklayarak makroyu çalıştırın
7. Makroyu durdurmak için "Durdur" butonuna tıklayın veya F10 tuşunu kullanın

## Tiklamalar.txt Dosyası

Tiklamalar.txt dosyası, programın kullanacağı tıklama koordinatlarını içerir. Dosya formatı aşağıdaki gibidir:

```
# Yorum satırı
x,y,delay_ms,is_right_click
```

Örnek:
```
# HP Pot (Kırmızı pot)
800,450,300,0

# MP Pot (Mavi pot)
850,450,300,0
```

Burada:
- x, y: Tıklanacak ekran koordinatları
- delay_ms: Tıklama sonrası bekleme süresi (milisaniye)
- is_right_click: 0=sol tık, 1=sağ tık

## Can Barı Tespiti Nasıl Çalışır?

Program, seçilen parti bölgesini 8 eşit yükseklikte bölgeye ayırarak her bir bölgenin bir parti üyesinin can barını temsil ettiğini varsayar. Her bölgedeki kırmızı piksel oranını analiz ederek can yüzdesini şu formülle hesaplar:

```
can_yuzdesi = (kirmizi_piksel_sayisi / toplam_bar_pikseli) * 100
```

Bu yüzde, belirlenen eşik değerinin altına düştüğünde program şunları yapar:
1. Can barının ortasına tıklar (üyeyi seçer)
2. İyileştirme butonuna tıklar

## Klavye Kısayolları

- **F10**: Makroyu başlat/durdur

## Sorun Giderme

- **Parti can barları algılanmıyor**: Parti bölgesini doğru seçtiğinizden emin olun
- **İyileştirme çalışmıyor**: İyileştirme konumunu doğru seçtiğinizden emin olun
- **Program yanıt vermiyor**: Programı yeniden başlatın
- **Hassasiyet sorunları**: İyileştirme eşiğini daha yüksek bir değere ayarlayın

## Yasal Uyarı

Bu program, sadece eğitim amaçlıdır. Kullanımından doğabilecek sonuçlardan kullanıcı sorumludur. Knight Online oyun kurallarını ihlal edebilecek şekilde kullanmayın. 