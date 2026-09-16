@echo off
REM Birlesik KO Yardimcisi - python ile calistirma.
REM exe uretimi icin (yalniz istenildiginde): build.bat

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python bulunamadi. https://www.python.org adresinden kurulmali
    echo ve PATH'e eklenmelidir.
    pause
    exit /b 1
)

python main.py
if errorlevel 1 (
    echo.
    echo Program hata koduyla kapandi. Yukaridaki mesajlari kontrol et.
    pause
)
