# Birleşik KO Yardımcısı

Tek uygulama, PyQt5, modül başına ayrı thread. Yalnızca **ekran okuma + sentetik
klavye/fare** kullanır; oyuna hiçbir şekilde enjeksiyon yapılmaz.

## Kurulum

```bash
python -m pip install -r requirements.txt
```

Interception **kernel sürücüsü** kuruluysa tuşlar donanım seviyesinde gönderilir.
Kurulu değilse program yine çalışır, PyAutoGUI/win32 yedeğine düşer ve açılışta
bir kez bunu söyler. Kullanılan arka uç her zaman **Bilgi** sekmesinde yazar.
(`interception.dll` C API kütüphanesidir; Python sarmalayıcı sürücüyle doğrudan
konuştuğu için asıl şart sürücünün kurulu olmasıdır.)

## Çalıştırma

```bash
calistir.bat
```

(veya doğrudan `python main.py`)

`profiles.ini` ilk kaydetmede otomatik oluşur. Ayarlar dosyaya **yalnızca
Kaydet** düğmesiyle yazılır; kaydetmeden kapatırsan uyarı çıkar.

## İlk kurulum sırası

1. Oyunu aç, programı başlat.
2. **Master**'a bir kez bas — ön plandaki pencerenin başlığı otomatik yakalanır
   (`Oyun penceresi` kutusundan sonradan düzeltebilirsin). Bu başlık ön planda
   değilken tarama ve tuş gönderimi durur.
3. **Kalibrasyon** sekmesi → *Çerçeveleri göster* (aynı düğme tekrar basınca
   gizler; kayıtlı çerçeveler de kaydedildikleri yer/boyutla açılır, böylece
   yerlerini kontrol edip gerekirse yeniden kaydedebilirsin). Beş çerçeve
   birden ekrana gelir:
   - `HP barı`, `MP barı` → **tam doluyken** kaydet. HP kaydında program
     barın bölge içindeki yerini kendisi çıkarır; çıkaramazsa kayıt reddedilir
     ve çerçeveyi düzeltmen istenir.
   - `Hedef (mob) barı` → **önce oyunda bir mob seç**, sonra kaydet.
   - `Parti barı` → çerçeve **tam 2 üyelik** alanı kapsamalı; satır yüksekliği
     bundan türetilir ve 8 üyeye kadar aşağı uzatılır. Kayıt sırasında
     **partide en az 2 kişi olmalı**: program iki üyenin barını ayrı ayrı
     bulup birbiriyle karşılaştırır, tutmuyorsa "çerçeve tam 2 üyeyi
     kapsamıyor" der. Kayıt bitince iki üyenin okunan canını gösterir —
     ikisi de tam canlıyken kaydettiysen %97-100 arası çıkmalı.
   - `Silah alanı` → çerçeveyi iki elindeki silahları kapsayacak şekilde koy
     ve **İKİ silah da tam yanıkken** kaydet. Tespit RENGE bakar: sonradan
     tek el yansa da, kılıcın yönü değişse de, arka plan ne renk olursa
     olsun tanınır.
   Her çerçevenin başlığında canlı okuma yazar ("şu an %97 okuyorum"); doğru
   okuduğunu gördükten sonra Kaydet'e bas, çerçeve kaybolur. Çerçeveler
   herhangi bir **kenardan veya köşeden sürüklenerek** boyutlandırılır.
4. Modül tikini aç. Gereken kalibrasyon yoksa tik geri kapanır ve eksik çerçeve
   ekrana gelir.

Çerçeveler ve overlay `WDA_EXCLUDEFROMCAPTURE` ile ekran yakalamadan çıkarılır,
bu yüzden barların üstünde dursalar bile ölçümü bozmazlar. Ana panel normal bir
penceredir: kalibre bir barın üzerine gelirse program seni bir kez uyarır.

## Denetimler

| Ne | Nerede |
|---|---|
| Master aç/kapa | Üstteki büyük düğme veya master kısayolu |
| Panik | Panik kısayolu — her şeyi anında durdurur, **yalnız master** geri açar |
| Modül aç/kapa | Her sekmenin üst şeridindeki *Aktif* tiki veya modül kısayolu |
| Döngü hızı | Her modülün kendi `Döngü` kutusu |
| Kompakt mod | *Kompakt* düğmesi; geri dönmek için master düğmesine çift tıkla |

Master kapatılıp açıldığında modül tikleri korunur. Program her açılışta master
**PASİF** başlar.

## Can barının rengi (debuff durumları)

Yaratıkların atağına göre can barının rengi değişiyor: yanarken **turuncu**,
light/zehir/malice/parasite grubunda **mor**, ice-yavaşlatmada **sarı-yeşil**.

Ölçüm bundan etkilenmez: program barın **dolu** kısmının rengine değil, **boş**
kısmına bakar. Boş kısım rengi ne olursa olsun siyah kaldığı için mor bir bar
da turuncu bir bar da doğru okunur. (Eskiden kayıt anındaki kırmızı tona maske
uygulanıyordu; renk değişince %0 okunup "öldük" alarmı çalıyordu.)

Renk ayrıca **Bilgi** sekmesinde ve overlay'de `Durum` olarak yazılır — parti
üyeleri için de. Bu yalnız bilgidir, **hiçbir otomatik karara bağlı değildir**;
heal ve pot yalnız yüzdeye bakar. Tanınmayan bir renk çıkarsa "bilinmeyen
durum" yazar, ölçüm yine doğru çalışır.

Renk tablosu `app/constants.py` içindeki `HP_STATES` listesidir; yeni bir renk
eklemek tek satırdır (tonlar OpenCV ölçeğinde 0-180).

## Parti üye sayısı

**Priest** sekmesindeki `Parti heal` kartında `Üye sayısı` seçilir:

* **Otomatik** — program satırları tarayıp sayar. Boş satırın arkası oyun
  dünyası olduğu için yanılabilir.
* **Solo (parti yok)** — parti hiç okunmaz, o maliyet tamamen kalkar.
* **N kişi** — yalnız o kadar satır okunur; sayım hatası da maliyeti de sıfır.

Sayıyı sen bildiğin için elle vermek hem daha güvenilir hem daha hızlıdır.

## Otomatik korumalar

- **Oyun odakta değil** → tarama ve tuş gönderimi durur.
- **Ölüm koruması**: HP 5 sn boyunca %0 kalır veya bar kaybolursa modüller
  duraklar + bip çalar; HP %5'in üstüne çıkınca kendiliğinden devam eder.
- **Çözünürlük değişti** → uyarı + master kapanır.
- **Modül 10 ardışık hata verirse** kendini durdurur, panoda kırmızı olur, bip
  çalar; diğer modüller etkilenmez.

Loglama yoktur (performans kararı) — her şey RAM içindeki LiveStatus'ta tutulur
ve **Bilgi** sekmesinde gösterilir.

## Test tezgâhı

Oyun olmadan test etmek için:

```bash
python tools/dummy_game_window.py
```

Başlığı ayarlanabilir sahte bir oyun penceresi açar: HP/MP/hedef barları,
2-8 parti satırı, sahte RPR ikonu ve aldığı tuşları/tıkları aralarındaki
süreyle listeleyen bir kayıt paneli.

Hepsini tek komutla çalıştır (her test ayrı süreçte, aralarında bekleme ile):

```bash
python tools/tests/hepsini_calistir.py
```

Ölçek (DPI) denemesini de ekle:

```bash
python tools/tests/hepsini_calistir.py --dpi
```

Tek tek çalıştırmak istersen (dummy pencereye karşı gerçek ekran okuma):

```bash
python tools/tests/test_moduller.py
```

```bash
python tools/tests/test_kalibrasyon.py
```

```bash
python tools/tests/test_uygulama.py
```

Bu üçü tuşları sahte bir girdi servisiyle kaydeder. Girdi yolunun kendisini
uçtan uca denemek için (gerçek tuş ve gerçek tık gönderir, dummy'nin kayıt
listesinden doğrular):

```bash
python tools/tests/test_gercek_girdi.py
```

Ölçek (DPI) denemesi — Qt'yi %125'e zorlayıp aynı testleri çalıştırır:

```bash
python tools/tests/test_rpr.py
```

Testler sırasında dummy pencereyi kapatan bir pencere olmamalı; script dummy'yi
kendisi en üste alır ve ön plana getirir.

## Paketleme (yalnız istenirse)

Normal kullanım python iledir; exe yalnız sen istediğinde üretilir:

```bash
build.bat
```

`dist\BirlesikKO.exe` ve yanına `interception.dll` üretir. Ayarlar
(`profiles.ini`) exe'nin yanına yazılır, geçici klasöre değil.

## Arayüz notları

- Skill / pot / heal / buff tuşları **yalnız 1-0 rakamlarıdır** (oyundaki hızlı
  erişim çubuğu). F sayfası ayrı bir kutudur; **—** seçeneği "sayfa değiştirme"
  demektir (eski adıyla "F Sayfası").
- Panel 240x480'e küçültüldü. Her sekme kaydırılabilir, hiçbir alan kesilmez.
- "Program ayarları" bloğu yalnız **Genel** sekmesinin altındadır; master düğmesi,
  tik satırı ve sekmeler her zaman üsttedir. Aktif süre master düğmesinde yazar.

## Sürüm notu (görüş düzeltmeleri)

Bar okuma HSV tabanlı yapıldı (KO'nun degrade MP barı ve koyu mavi boş kısmı
için) ve parti üye tespiti oyun dünyası zeminine dayanıklı hale getirildi.
**MP ve parti kalibrasyonunu bir kez yeniden kaydetmen önerilir** — eski
kayıtlar da çalışır ama yeni doygun-renk örneklemesi kayıt anında daha isabetli
referans seçer.
