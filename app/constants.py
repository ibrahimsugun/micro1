"""Uygulama geneli sabitler.

Buradaki sayısal değerler anket kararlarıdır; koddan değiştirilmez.
"""

APP_NAME = "Birleşik KO Yardımcısı"
APP_VERSION = "1.0"
SINGLE_INSTANCE_MUTEX = "BirlesikKOYardimcisi_TekKopya_Mutex"

# --- Interception tarama kodları (micro1-master/combined.py:44 ile birebir) ---
KEYCODES = {
    "F1": 0x3B, "F2": 0x3C, "F3": 0x3D, "F4": 0x3E, "F5": 0x3F, "F6": 0x40,
    "F7": 0x41, "F8": 0x42, "F9": 0x43, "F10": 0x44, "F11": 0x57, "F12": 0x58,
    "F13": 0x64, "F14": 0x65, "F15": 0x66,
    "0": 0x0B, "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
    "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0A,
    "A": 0x1E, "B": 0x30, "C": 0x2E, "D": 0x20, "E": 0x12, "F": 0x21,
    "G": 0x22, "H": 0x23, "I": 0x17, "J": 0x24, "K": 0x25, "L": 0x26,
    "M": 0x32, "N": 0x31, "O": 0x18, "P": 0x19, "Q": 0x10, "R": 0x13,
    "S": 0x1F, "T": 0x14, "U": 0x16, "V": 0x2F, "W": 0x11, "X": 0x2D,
    "Y": 0x15, "Z": 0x2C,
}

# Eylem tuşu olarak seçilebilecekler: YALNIZ hızlı erişim çubuğu rakamları.
# (Kullanıcı kararı: skill/pot/heal tuşları oyunda 1-0 arasındadır; harf ve F
# tuşları listeyi gereksiz kabartıyordu. KEYCODES tam kalır — R, Z ve F sayfası
# tuşları modüller tarafından doğrudan gönderilir.)
ACTION_KEYS = [str(d) for d in range(1, 10)] + ["0"]

# --- F sayfaları ---
NO_PAGE = "F Sayfası"          # "geçiş yok" anlamına gelen seçenek
F_PAGES = [NO_PAGE, "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8"]

# --- Zamanlama sabitleri (anket kararları) ---
KEY_HOLD_MIN_MS = 30           # insansı tuş basılı tutma alt sınırı
KEY_HOLD_MAX_MS = 80           # insansı tuş basılı tutma üst sınırı
PAGE_SWITCH_WAIT_MS = 100      # F sayfası → tuş arası bekleme
POT_KEY_COOLDOWN_MS = 1320     # aynı pot tuşu için bekleme
ATTACK_RANDOM_MAX_DEFAULT = 531
ATTACK_NATURAL_JITTER = 0.10   # rastgele tik kapalıyken bile ±%10 sapma
R_ATTACK_INTERVAL_MS = 1000    # bağımsız sabit R sayacı
RPR_REPEAT_MS = 5000           # ikon duruyorsa tekrar denemeden önce
Z_MIN_MS = 647                 # Z aralığı alt sınırı (sıradaki mobu erken seç)
Z_MAX_MS = 1007                # Z aralığı üst sınırı
HEAL_MEMBER_COOLDOWN_MS = 2000 # aynı parti üyesine tekrar heal beklemesi
DEATH_HOLD_SECONDS = 5.0       # HP %0 / bar yok bu süre boyunca sürerse ölüm
DEATH_RECOVER_PERCENT = 5.0    # bu yüzdenin üstüne çıkınca ölüm durumu kalkar
PARTY_RESCAN_MS = 3000         # otomatik parti üye taraması
MAX_MODULE_ERRORS = 10         # modül kendini durdurmadan önceki ardışık hata
THREAD_JOIN_TIMEOUT = 2.0

# --- Modül varsayılan döngü hızları (ms) ---
DEFAULT_LOOP_MS = {
    "pot": 100,
    "attack": 50,
    "heal": 100,
    "buff": 250,
    "clicker": 10,
}
LOOP_MS_MIN = 10
LOOP_MS_MAX = 2000

# --- Görüntü işleme ---
COLOR_TOLERANCE = 30           # referans renge tolerans (kanal başına)
TARGET_PRESENT_RATIO = 2.0     # target_bar bu oranın üstündeyse hedef var
PRESENCE_STD_MIN = 8.0         # boş satır / gerçek üye ayrımı (std sapma)
TEMPLATE_MATCH_THRESHOLD = 0.85  # eski şablon kayıtları için (geriye dönük)
# RPR: yanık silah RENKTEN tanınır (şekil/yön/hangi el fark etmez).
# Kayıt anındaki yanık oranının bu katına ulaşınca "kırık" sayılır.
# 0.30 seçildi: iki silah yanıkken kaydedilip TEK silah yanarsa oran ~0.50
# olur, animasyonla daralsa bile eşiği geçer; zemindeki dağınık kırmızı ise
# bu orana ulaşamaz.
RPR_TRIGGER_FRACTION = 0.30

# Yanık silahın TAM YANDIĞINDAKİ SABİT kırmızısı (BGR). 10 gerçek ekran
# görüntüsünden ölçüldü (tools/tests/ornekler/rpr_yanik): ton ~0, yüksek
# doygunluk; parlaklık arka plana göre 128-183 değişse de HSV bandı kapsar.
# Silah durability düşerken yavaşça kırmızıya "dalgalanır", TAM yanınca bu
# sabit renkte durur. Bu yüzden referans kayıt anındaki DEĞİŞKEN renk değil,
# bu SABİT değerdir: yalnız tam yanık (doygun kırmızı) yakalanır, ara
# dalgalanma (soluk) değil. Kayıt/arka plan hatalarından da bağımsızdır.
RPR_BURNT_COLOR_BGR = (30, 35, 150)
SCANNER_FPS = 10.0

# --- Bar tümdengelim ölçümü (renkten BAĞIMSIZ) ---
# HP barının rengi debuff'a göre değişiyor (mor / turuncu / sarı-yeşil). Dolu
# kısmın rengine bakan ölçüm bu durumda %0 okuyup "öldük" alarmı veriyordu.
# Bu yüzden HP ailesinde barın BOŞ kısmı sayılır: boş kısım rengi ne olursa
# olsun siyah kalır. Gerçek oyun görüntülerinden ölçüldü (tools/tests/ornekler):
# dolu bölge V = 86..167, boş bölge V = 0..45.
BAR_DARK_VALUE_MAX = 60           # parlaklık (V) bunun altındaysa piksel "boş"
BAR_COLUMN_EMPTY_FRACTION = 0.60  # sütunun bu oranı karanlıksa sütun boş sayılır
BAR_BAND_MIN_ROWS = 2             # ölçüm şeridi en az bu kadar satır olmalı
BAR_LIT_SAT_MIN = 60              # "barda hâlâ ışık var mı" (ölüm koruması emniyeti)
BAR_LIT_VALUE_MIN = 70

# HP barı renk durumları — YALNIZ BİLGİ amaçlı etiket; hiçbir otomatik karara
# bağlı değildir. Tonlar OpenCV ölçeğinde (0-180) ve gerçek oyun ekran
# görüntülerinden ölçülmüştür. Yeni renk eklemek için tabloya tek satır yeter.
HP_STATE_HUE_TOLERANCE = 8        # normal(0) ile yanma(17.6) arası 17.6 -> 8 güvenli
HP_STATES = (
    ("normal", "normal", 0.0),
    ("yanma", "yanma", 17.6),
    ("yavaslatma", "ice / yavaşlatma", 38.4),
    ("mor", "mor (malice/parasite/zehir/light)", 148.5),
)
HP_STATE_UNKNOWN = "bilinmeyen"
HP_STATE_LABELS = {key: label for key, label, _hue in HP_STATES}

# --- Kalibrasyon bölgeleri ---
CALIB_HP = "hp_bar"
CALIB_MP = "mp_bar"
CALIB_TARGET = "target_bar"
CALIB_PARTY = "party_bar"
CALIB_RPR = "rpr_icon"

CALIB_LABELS = {
    CALIB_HP: "HP Barı",
    CALIB_MP: "MP Barı",
    CALIB_TARGET: "Hedef (Mob) Barı",
    CALIB_PARTY: "Parti Barı (tam 2 üyelik alan)",
    CALIB_RPR: "Silah alanı (İKİ silah da YANIKKEN kaydet)",
}

CALIB_COLORS = {
    CALIB_HP: "#c0392b",
    CALIB_MP: "#2471a3",
    CALIB_TARGET: "#b7950b",
    CALIB_PARTY: "#1e8449",
    CALIB_RPR: "#7d3c98",
}

CALIB_ORDER = [CALIB_HP, CALIB_MP, CALIB_TARGET, CALIB_PARTY, CALIB_RPR]

# Şablon (renk yerine görüntü) ile kaydedilen bölge KALMADI; RPR de renkle
# çalışıyor. Eski şablonlu kayıtlar okunmaya devam eder (geriye dönük).
TEMPLATE_REGIONS = set()

MAX_PARTY_MEMBERS = 8
PARTY_CALIB_ROWS = 2           # party_bar kaydı tam 2 üyeyi kapsar

# --- Modül kimlikleri ve gerekli kalibrasyonlar ---
MODULE_POT = "pot"
MODULE_ATTACK = "attack"
MODULE_HEAL = "heal"
MODULE_BUFF = "buff"
MODULE_CLICKER = "clicker"

MODULE_LABELS = {
    MODULE_POT: "Genel (Pot)",
    MODULE_ATTACK: "Atak",
    MODULE_HEAL: "Priest (Heal)",
    MODULE_BUFF: "Priest (Buff)",
    MODULE_CLICKER: "Diğer (Tıklayıcı)",
}

# --- Ses ---
BEEP_DEATH = (600, 250)        # (frekans Hz, süre ms)
BEEP_ERROR = (1100, 150)
BEEP_PANIC = (400, 400)
