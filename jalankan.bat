@echo off
REM ============================================================
REM  Asisten Random Sampling - Launcher (Windows)
REM  Klik dua kali file ini untuk menjalankan aplikasi.
REM ============================================================
cd /d "%~dp0"
echo Memeriksa dependensi...
python -m pip install -q -r requirements.txt
echo.
echo Membuka aplikasi di browser...
python -m streamlit run app.py
pause
