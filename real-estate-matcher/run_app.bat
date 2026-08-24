@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo   AI Emlak Ilan Eslestirme ve Portfoy Zekasi
echo ========================================================

if not exist ".venv\Scripts\python.exe" (
    echo Ilk kurulum yapiliyor. Bu islem birkac dakika surebilir...
    python -m venv .venv
    if errorlevel 1 goto :setup_error
)

".venv\Scripts\python.exe" -c "import streamlit, pandas, google.genai, pydantic" >nul 2>&1
if errorlevel 1 (
    echo Gerekli paketler yukleniyor...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :setup_error
)

echo Uygulama aciliyor: http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run app.py --browser.gatherUsageStats false
goto :end

:setup_error
echo.
echo Kurulum tamamlanamadi. Python 3.11 veya daha yeni bir surumun kurulu oldugunu kontrol edin.
pause
exit /b 1

:end
pause
