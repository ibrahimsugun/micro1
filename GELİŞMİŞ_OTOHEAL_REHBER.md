# Gelişmiş Otomatik İyileştirme ve Buff Sistemi Kullanım Rehberi

Bu rehber, Knight Online için geliştirilmiş Otomatik İyileştirme ve Buff sisteminin kullanımını açıklamaktadır.

## Temel Özellikleri

### 1. Çoklu HP Barı Takibi
- 8 ayrı satırda bağımsız HP barı takibi yapabilir
- Her satır için ayrı koordinatlar belirlenebilir
- Her satır bağımsız olarak aktif/pasif yapılabilir

### 2. Merkezi HP Yüzdesi Kontrolü
- Tüm satırlar için ortak bir HP yüzdesi eşiği kullanılır
- HP bu yüzdenin altına düştüğünde otomatik iyileştirme yapılır

### 3. Buff Sistemi
- Merkezi bufflar ve özel bufflar eklenebilir
- Her buff için ayrı süre ve koordinat ataması yapılabilir
- Buffları kalıcı olarak kaydetme ve yükleme imkanı
- Buffların aktif/pasif durumunu tek tıkla değiştirme

## Kullanım Adımları

### 1. Oto Heal Koordinatlarının Belirlenmesi

1. "Oto Heal + Buff" sekmesine geçin
2. İzlemek istediğiniz satırların kutucuklarını işaretleyin
3. Her satır için "X. Sıra Koordinat Al" butonuna tıklayın
4. Ekranda izlemek istediğiniz HP barının **SOL** ucuna gelin ve CTRL tuşuna basın
5. Ardından aynı HP barının **SAĞ** ucuna gelin ve CTRL tuşuna basın
6. İşlem başarılı olduğunda koordinatlar ekranda görünecektir

### 2. HP Yüzdesinin Ayarlanması

1. Üst kısımdaki "HP %" değerini istediğiniz seviyeye ayarlayın (örn: 80%)
2. Bu değer, HP barlarının doluluk oranı bu yüzdenin altına düştüğünde müdahale edileceğini belirtir

### 3. Buff Sisteminin Kullanımı

**Merkezi Buff Sistemi (Ayarlar Sekmesi):**
1. Buff ve AC için ayrı tuşları ayarlayabilirsiniz
2. Süreleri saniye cinsinden belirleyin
3. Aktif kutucuğunu işaretleyerek buff'ın otomatik olarak atılmasını sağlayın

**Özel Buff Yönetimi (Buff Listesi):**
1. "Buff Ekle" butonuna tıklayarak yeni bir buff ekleyin
2. Buff'a bir isim verin (örn: "Kabin", "Güç Kalkanı" vb.)
3. Süreyi saniye cinsinden belirleyin
4. "Koordinat Seç" butonuyla, buff'ın ekrandaki yerini belirleyin
5. "Aktif" kutucuğunu işaretleyerek buff'ı etkinleştirin
6. "Buffları Kaydet" butonuyla tüm buffları kaydedin
7. "Buffları Yükle" butonuyla önceden kaydedilmiş buffları yükleyin

### 4. Sistemin Başlatılması ve Durdurulması

1. Tüm ayarları yaptıktan sonra "Başlat" butonuna tıklayın
2. Sistem çalışmaya başladığında düşük HP'li karakterleri otomatik olarak iyileştirecek
3. "Durdur" butonuna tıklayarak sistemi istediğiniz zaman durdurabilirsiniz
4. "Ayarları Kaydet" butonuna tıklayarak ayarlarınızı kaydedebilirsiniz

## Önemli Notlar

- Koordinatları belirlerken HP barlarının **tam olarak başlangıç ve bitiş noktalarını** seçmeye özen gösterin
- Buff'ları kaydetmeyi unutmayın, aksi halde program yeniden başlatıldığında kaybolurlar
- Program, Knight Online'ın çalıştığı pencere üzerinde en iyi performansı gösterir
- Eğer koordinat alınamıyorsa, oyun penceresini tam ekran değil, pencere modunda çalıştırmayı deneyin

## Bilinen Sorunlar ve Çözümleri

### HP Takip Sistemi Sorunları
- **Ekran görüntüsü alınırken hata**: "MSS ile ekran görüntüsü alınırken hata: '_thread._local' object has no attribute 'srcdc'" mesajı görebilirsiniz. Bu hata program çalışmasını etkilemez, program alternatif yöntemle ekran görüntüsünü alacaktır.
- **HP barı analiz hatası**: Program, HP barını doğru algılayamadığında sürekli iyileştirme yapabilir. Bu durumda:
  - Koordinatları yeniden belirleyin
  - HP yüzdesini daha düşük bir değere ayarlayın
  - HP barının temiz görünür olduğundan emin olun
  - Oyunu pencere modunda çalıştırmayı deneyin

### Buff Sistemi Sorunları
- **Yeni eklenen bufflar hemen görüntülenmeyebilir**: "Buffları Yükle" butonuna tıklayarak listeyi yenileyin
- **Buff sürelerinin doğru hesaplanması**: Buff'ı aktif etmeden önce süreyi doğru ayarlayın
- **Buff listesi doğru yüklenmiyor**: `buffs.json` dosyasının aynı dizinde olduğundan emin olun

### Performans Sorunları
- Çok fazla HP barı izleme program performansını etkileyebilir, sadece ihtiyacınız olan satırları aktif edin
- Buff sayısını sınırlı tutun
- Çok kısa sürelerde buff yenileme işlemi performansı etkileyebilir, süreleri en az 5 saniye yapın

## Sorun Giderme

1. **Program başlarken hata veriyorsa**: 
   - Programı yönetici olarak çalıştırın: `py -3 auto_heal_main.py`
   - PyQt5, MSS, numpy ve pyautogui kütüphanelerinin yüklü olduğundan emin olun
   - Windows PowerShell veya Komut İstemi'ni kullanın

2. **Koordinatlar alınamıyorsa**: 
   - Oyunu pencere modunda çalıştırın
   - CTRL tuşunu basılı tutmak yerine, hızlıca basıp bırakın
   - Farklı bir klavye kullanmayı deneyin

3. **Buff listesi görünmüyorsa**:
   - Buff listesi bölümünü genişletin
   - Programı yeniden başlatın
   - `buffs.json` dosyasını kontrol edin

4. **Ayarlar kaydedilmiyorsa**:
   - Programın çalıştığı klasöre yazma izninin olduğundan emin olun
   - `settings.ini` dosyasını silin ve yeniden oluşturun

5. **Ekran görüntüsü hataları**:
   - Program hata bildirse bile çalışmaya devam edecektir
   - Farklı ekran çözünürlüklerinde sorun yaşanabilir, standart çözünürlükte deneyin (1920x1080)

---

Program sürekli geliştirilmektedir. Yeni sürümlerde performans iyileştirmeleri ve hata düzeltmeleri yapılacaktır. 