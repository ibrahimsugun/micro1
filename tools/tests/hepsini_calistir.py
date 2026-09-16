"""Tüm testleri sırayla, birbirini bozmadan çalıştırır.

Testler gerçek ekranı okuyor: bir testin penceresi kapanmadan diğeri açılırsa
dummy pencere örtülür ve ölçümler yanlış çıkar. Bu yüzden her test AYRI süreçte
ve aralarında bekleme ile çalıştırılır; bir test düşerse bir kez tekrarlanır
(gerçek hatalar tekrarda da düşer, örtüşme dalgalanmaları düzelir).

Kullanım:
    python tools/tests/hepsini_calistir.py            # %100 ölçek
    python tools/tests/hepsini_calistir.py --dpi      # %100 + %125 ölçek
    python tools/tests/hepsini_calistir.py --girdi    # + gerçek tuş/tık testi

--girdi verilmedikçe hiçbir test gerçek tuş/tık göndermez; bilgisayarı
kullanırken güvenle çalıştırılabilir.
"""

import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

# Varsayilan kosu: hicbiri gercek tus/tik gondermez, yalniz ekran okur.
TESTS = [
    "test_ornek_goruntuler.py",   # cevrimdisi: gercek oyun PNG'leri, pencere acmaz
    "test_rpr_gercek.py",         # cevrimdisi: gercek yanik silah goruntuleri
    "test_moduller.py",
    "test_kalibrasyon.py",
    "test_debuff_renk.py",
    "test_rpr.py",
    "test_uygulama.py",
    "test_pencere_yakalama.py",   # arka plan modu: pencere bulma/yakalama/kapi
]

# GERCEK fare tiklamasi ve tus gonderir, fare imlecini oynatir. Bilgisayari
# kullanirken calistirilmamali; yalnizca --girdi ile istege bagli eklenir.
INPUT_TESTS = ["test_gercek_girdi.py"]

SUMMARY = re.compile(r"Toplam\s+(\d+)\s+kontrol,\s+(\d+)\s+ba", re.IGNORECASE)
GAP_SECONDS = 4.0


def say(text=""):
    """Konsol kod sayfasi (cp1254) her karakteri basamayabilir; kirpip yaz."""
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "ascii"
        print(text.encode(encoding, "replace").decode(encoding))


def run_once(path, scale):
    env = dict(os.environ)
    if scale:
        env["QT_SCALE_FACTOR"] = scale
    else:
        env.pop("QT_SCALE_FACTOR", None)
    proc = subprocess.run(
        [sys.executable, path], cwd=ROOT, env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    match = None
    for match in SUMMARY.finditer(output):
        pass
    if match is None:
        skipped = "atlaniyor" in output or "atlanıyor" in output
        return None if skipped else (0, 1), output
    return (int(match.group(1)), int(match.group(2))), output


def run_suite(scale, tests):
    label = "%125" if scale else "%100"
    say("=" * 62)
    say("OLCEK {}".format(label))
    say("=" * 62)
    total = failed = skipped = 0
    problems = []
    for name in tests:
        path = os.path.join(HERE, name)
        time.sleep(GAP_SECONDS)
        result, output = run_once(path, scale)
        if result is None:                       # odak alinamadi -> tekrar dene
            time.sleep(GAP_SECONDS)
            result, output = run_once(path, scale)
        if result is None:
            say("  {:<26} ATLANDI (pencere on plana alinamadi)".format(name))
            skipped += 1
            continue
        count, bad = result
        if bad:                                  # bir kez daha sans ver
            time.sleep(GAP_SECONDS)
            retry, retry_out = run_once(path, scale)
            if retry is not None:
                count, bad = retry
                output = retry_out
        total += count
        failed += bad
        status = "OK" if bad == 0 else "{} BASARISIZ".format(bad)
        say("  {:<26} {:>3} kontrol  {}".format(name, count, status))
        if bad:
            for line in output.splitlines():
                if "BASARISIZ:" in line:
                    problems.append("    " + line.strip())
    for line in problems:
        say(line)
    say("  -> {} kontrol, {} basarisiz, {} atlandi".format(total, failed, skipped))
    return failed


def main():
    scales = [""]
    if "--dpi" in sys.argv:
        scales.append("1.25")
    tests = list(TESTS)
    if "--girdi" in sys.argv:
        tests += INPUT_TESTS
        say("UYARI: --girdi verildi; gercek tus/tik gonderilecek, "
            "bilgisayari birak.")
    failed = 0
    for scale in scales:
        failed += run_suite(scale, tests)
    say("")
    say("SONUC: {}".format("TUM TESTLER GECTI" if failed == 0
                             else "{} BASARISIZ".format(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
