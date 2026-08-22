@echo off
cd /d "%~dp0"
start "" http://localhost:8502
.venv\Scripts\python.exe -m streamlit run app.py --server.port 8502
