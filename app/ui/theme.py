"""Arayüz tasarım sistemi: renk paleti + tek merkezi stil sayfası.

Tasarım kararları:
  * Açık, sakin bir zemin üzerinde beyaz "kart"lar. Ağır çerçeveli QGroupBox
    yerine yumuşak kenarlı kartlar ve üstlerinde küçük bölüm başlıkları.
  * Tek vurgu rengi (mavi) seçim/odak için; yeşil-kırmızı yalnızca DURUM için
    ayrılmıştır, böylece renk anlam taşır.
  * Sekmeler doldurulmuş bir bölmeli denetim gibi: seçili sekme vurgu rengiyle
    dolu, bakışta belli olur.
  * Tüm girdi kutuları aynı yükseklikte (26 px) ve aynı köşe yuvarlaklığında;
    dikey ritim 6/8 px katları.
"""

# ------------------------------------------------------------------ palet
BG = "#eef1f7"           # pencere zemini
CARD = "#ffffff"         # kart yüzeyi
CARD_ALT = "#f8fafc"     # ikincil yüzey (satır zebra, pasif alan)
BORDER = "#d9dfea"       # ince ayraç
BORDER_STRONG = "#bcc5d6"
TEXT = "#111827"         # ana metin
MUTED = "#475263"        # ikincil metin (alan etiketleri, ipuçları)
FAINT = "#6a7480"        # üçüncül metin (bölüm başlığı, sıra no)

ACCENT = "#2563eb"       # vurgu (seçim, odak, birincil düğme)
ACCENT_HOVER = "#1d4fd7"
ACCENT_SOFT = "#e7efff"

GREEN = "#0f7442"        # durum: çalışıyor / sağlam
GREEN_SOFT = "#e6f6ed"
GREEN_BORDER = "#9dd8b8"
RED = "#c3302a"          # durum: durdu / hata / kırık
RED_SOFT = "#fdecea"
RED_BORDER = "#f0b0ab"
AMBER = "#9a6408"        # durum: bekliyor
AMBER_SOFT = "#fdf3e2"

FONT = '"Segoe UI", "Segoe UI Variable", sans-serif'

# Kart içi standart ölçüler (yerleşim kodu da bunları kullanır)
CARD_MARGIN = 11
CARD_SPACING = 7
ROW_SPACING = 6
INPUT_HEIGHT = 28


def _asset(name):
    """Paket içi görsel yolu (PyInstaller onefile'da _MEIPASS altında)."""
    import os
    import sys

    base = getattr(sys, "_MEIPASS", None)
    if base:
        path = os.path.join(base, "app", "ui", "assets", name)
    else:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", name)
    return path.replace("\\", "/")


CHECK_SVG = _asset("check.svg")


APP_QSS = """
* {{ outline: 0; }}

QWidget {{
    background-color: {bg};
    color: {text};
    font-family: {font};
    font-size: 13px;
}}

QToolTip {{
    background-color: #232937;
    color: #f2f4f8;
    border: none;
    border-radius: 5px;
    padding: 6px 8px;
    font-size: 11px;
}}

/* ----------------------------------------------------------------- kart */
QFrame#card {{
    background-color: {card};
    border: 1px solid {border};
    border-radius: 12px;
}}
QFrame#cardFlat {{
    background-color: {card_alt};
    border: 1px solid {border};
    border-radius: 8px;
}}
QLabel#sectionTitle {{
    color: {accent};
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.6px;
    padding: 1px 2px 2px 2px;
}}
QLabel#hint {{
    color: {muted};
    font-size: 12px;
}}
QLabel {{ background: transparent; }}
QLabel#fieldLabel {{
    color: {muted};
    font-size: 12px;
    font-weight: 600;
}}
QFrame#divider {{
    background-color: {border};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}

/* -------------------------------------------------------------- girdiler
   Not: açılır ok ve artır/azalt okları BİLEREK biçimlendirilmiyor —
   Qt stil sayfasında kenarlık-üçgeni hilesi çalışmıyor, kutu gibi
   görünüyorlardı. Fusion kendi oklarını düzgün çiziyor. */
QComboBox, QSpinBox, QLineEdit {{
    background-color: {card};
    border: 1px solid {border_strong};
    border-radius: 7px;
    padding: 2px 5px;
    font-size: 12px;
    min-height: {input_h}px;
    max-height: {input_h}px;
    color: {text};
    selection-background-color: {accent};
    selection-color: #ffffff;
}}
QComboBox:hover, QSpinBox:hover, QLineEdit:hover {{
    border-color: {faint};
}}
QComboBox:focus, QSpinBox:focus, QLineEdit:focus {{
    border-color: {accent};
}}
QComboBox QAbstractItemView {{
    background-color: {card};
    border: 1px solid {border_strong};
    border-radius: 6px;
    padding: 3px;
    selection-background-color: {accent_soft};
    selection-color: {text};
    outline: 0;
}}

/* -------------------------------------------------------------- düğmeler */
QPushButton {{
    background-color: {card};
    border: 1px solid {border_strong};
    border-radius: 8px;
    padding: 3px 12px;
    font-weight: 600;
    min-height: {input_h}px;
    color: {text};
}}
QPushButton:hover {{ background-color: {card_alt}; border-color: {faint}; }}
QPushButton:pressed {{ background-color: {accent_soft}; border-color: {accent}; }}
QPushButton:disabled {{ color: {faint}; background-color: {card_alt}; }}

QPushButton#primary {{
    background-color: {accent};
    border: 1px solid {accent};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background-color: {accent_hover}; border-color: {accent_hover}; }}
QPushButton#primary:disabled {{ background-color: #9db7f5; border-color: #9db7f5; color: #eef3ff; }}

QPushButton#danger {{
    background-color: {red_soft};
    border: 1px solid {red_border};
    color: {red};
}}
QPushButton#danger:hover {{ background-color: #fbdcd8; }}

QPushButton#go {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1f9d5c, stop:1 {green});
    border: 1px solid {green};
    border-radius: 10px;
    color: #ffffff;
    font-size: 15px;
    font-weight: 800;
    padding: 10px 8px;
}}
QPushButton#go:hover {{ background-color: #12844c; }}
QPushButton#go:disabled {{ background-color: #9fcfb5; border-color: #9fcfb5; }}

/* Sekme gezintisi: iki satırlık hap düğmeler (yazılar asla kesilmez) */
QFrame#navBar {{
    background-color: #e2e7f1;
    border: 1px solid {border};
    border-radius: 11px;
}}
QPushButton#navButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    color: {muted};
    font-size: 12px;
    font-weight: 700;
    padding: 5px 2px;
    min-height: 22px;
}}
QPushButton#navButton:hover {{ background-color: #f4f6fb; color: {text}; }}
QPushButton#navButton:checked {{
    background-color: {card};
    border: 1px solid {border_strong};
    color: {accent};
}}

QPushButton#ghost {{
    background-color: transparent;
    border: 1px solid transparent;
    color: {muted};
    padding: 2px 6px;
}}
QPushButton#ghost:hover {{ background-color: {card_alt}; color: {text}; }}

QPushButton#iconButton {{
    background-color: {card};
    border: 1px solid {border_strong};
    border-radius: 12px;
    padding: 0;
    color: {muted};
    font-size: 16px;
}}
QPushButton#iconButton:hover {{ color: {text}; border-color: {faint}; }}

/* Master: en üstteki ana anahtar, tek DOLU renk alan */
QPushButton#masterOn {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1fa463, stop:1 {green});
    border: 1px solid {green};
    border-radius: 12px;
    color: #ffffff;
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 0.5px;
    padding: 12px 8px;
}}
QPushButton#masterOn:hover {{ background-color: #12844c; }}
QPushButton#masterOff {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #de4a43, stop:1 {red});
    border: 1px solid {red};
    border-radius: 12px;
    color: #ffffff;
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 0.5px;
    padding: 12px 8px;
}}
QPushButton#masterOff:hover {{ background-color: #b02a25; }}

/* Modül anahtarı: master'ın SOLGUN kardeşi (alt seviye olduğu belli) */
QPushButton#moduleOn {{
    background-color: {green_soft};
    border: 1px solid {green_border};
    color: {green};
    font-weight: 600;
}}
QPushButton#moduleOn:hover {{ background-color: #dcf1e6; }}
QPushButton#moduleOff {{
    background-color: {card_alt};
    border: 1px solid {border_strong};
    color: {muted};
    font-weight: 600;
}}
QPushButton#moduleOff:hover {{ background-color: #eef1f6; color: {text}; }}
QPushButton#moduleError {{
    background-color: {red_soft};
    border: 1px solid {red_border};
    color: {red};
    font-weight: 600;
}}

/* --------------------------------------------------------------- tikler */
QCheckBox {{ spacing: 6px; color: {text}; background: transparent; }}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {border_strong};
    border-radius: 4px;
    background-color: {card};
}}
QCheckBox::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
    image: url("{check_svg}");
}}
QCheckBox:disabled {{ color: {faint}; }}

/* ------------------------------------------------------------- sekmeler */
QTabWidget::pane {{
    border: none;
    background: transparent;
    top: 2px;
}}
QTabBar {{ qproperty-drawBase: 0; background: transparent; }}
QTabBar::tab {{
    background-color: #e4e9f2;
    color: {muted};
    border: 1px solid #d3dae8;
    border-radius: 8px;
    padding: 11px 6px;
    margin-right: 3px;
    font-size: 12px;
    font-weight: 700;
}}
QTabBar::tab:hover:!selected {{ background-color: #d3dae8; color: {text}; }}
QTabBar::tab:selected {{
    background-color: {accent};
    color: #ffffff;
    border: 1px solid {accent};
    font-weight: 700;
}}

/* ---------------------------------------------------------- kaydırıcılar */
QSlider::groove:horizontal {{
    height: 4px;
    background: #dfe4ec;
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {accent};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {card};
    border: 2px solid {accent};
    width: 11px;
    height: 11px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{ border-color: {accent_hover}; }}

QScrollBar:vertical {{
    background: transparent;
    width: 9px;
    margin: 2px 0;
}}
QScrollBar::handle:vertical {{
    background: #ccd3df;
    border-radius: 4px;
    min-height: 26px;
}}
QScrollBar::handle:vertical:hover {{ background: {faint}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

QListWidget {{
    background-color: {card};
    border: 1px solid {border_strong};
    border-radius: 6px;
    padding: 2px;
    font-size: 11px;
}}
QListWidget::item {{ padding: 3px 4px; border-radius: 4px; }}
QListWidget::item:selected {{ background-color: {accent_soft}; color: {text}; }}

QMessageBox, QInputDialog {{ background-color: {card}; }}
""".format(
    bg=BG, card=CARD, card_alt=CARD_ALT, border=BORDER, border_strong=BORDER_STRONG,
    text=TEXT, muted=MUTED, faint=FAINT, accent=ACCENT, accent_hover=ACCENT_HOVER,
    accent_soft=ACCENT_SOFT, green=GREEN, green_soft=GREEN_SOFT,
    green_border=GREEN_BORDER, red=RED, red_soft=RED_SOFT, red_border=RED_BORDER,
    font=FONT, input_h=INPUT_HEIGHT, check_svg=CHECK_SVG,
)


def apply_theme(app):
    """Tasarım sistemini uygulamaya kurar (main.py buradan çağırır)."""
    app.setStyleSheet(APP_QSS)


def state_color(state: str) -> str:
    """Modül durumu -> metin rengi."""
    return {
        "running": GREEN,
        "waiting": AMBER,
        "error": RED,
    }.get(state, MUTED)


def state_soft(state: str) -> str:
    """Modül durumu -> yumuşak zemin rengi."""
    return {
        "running": GREEN_SOFT,
        "waiting": AMBER_SOFT,
        "error": RED_SOFT,
    }.get(state, CARD_ALT)
