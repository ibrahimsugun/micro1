@echo off
"C:\Users\getir\AppData\Local\Programs\Python\Python312\python.exe" -m pip uninstall pathlib -y
"C:\Users\getir\AppData\Local\Programs\Python\Python312\python.exe" -m PyInstaller --onefile --noconsole --icon=NONE --name KnightOnlineMacro combined.py
copy settings.ini dist\settings.ini
pause 