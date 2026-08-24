@echo off
cd /d "%~dp0"
echo ========================================================
echo   AI Emlak Ilan Eslestirme ve Portfoy Zekasi
echo ========================================================
echo   Uygulama baslatiliyor...
echo   Tarayiciniz otomatik acilacaktir.
echo   Adres: http://localhost:8501
echo ========================================================
echo.
"%~dp0.venv\Scripts\python.exe" -m streamlit run app.py --browser.gatherUsageStats false
pause

