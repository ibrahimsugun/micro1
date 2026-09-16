@echo off
REM Birlesik KO Yardimcisi - tek dosyalik exe uretimi.
REM
REM NOT: interception.dll C API kutuphanesidir; Python sarmalayici surucuye
REM dogrudan DeviceIoControl ile konusur. Asil sart, Interception KERNEL
REM SURUCUSUNUN sistemde kurulu olmasidir (install-interception.exe /install).
REM Surucu yoksa program calisir ama PyAutoGUI/win32 yedegine duser.

cd /d "%~dp0"

REM pyinstaller.exe PATH'te olmayabilir; modul olarak cagiriyoruz.
python -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo PyInstaller bulunamadi. Once su komutu calistir:
    echo     python -m pip install pyinstaller
    pause
    exit /b 1
)

python -m PyInstaller --noconfirm --clean ^
    --onefile ^
    --windowed ^
    --name "BirlesikKO" ^
    --add-binary "interception.dll;." ^
    --hidden-import pynput.keyboard._win32 ^
    --hidden-import pynput.mouse._win32 ^
    main.py

if errorlevel 1 (
    echo Derleme basarisiz.
    pause
    exit /b 1
)

copy /Y interception.dll dist\interception.dll >nul

echo.
echo Bitti. Cikti: dist\BirlesikKO.exe (+ dist\interception.dll)
echo Temiz bir klasore bu iki dosyayi kopyalayip ayni senaryoyu tekrarla.
echo Ayarlar (profiles.ini) exe'nin YANINA yazilir.
pause
