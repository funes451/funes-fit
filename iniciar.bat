@echo off
chcp 65001 > nul
cd /d "%~dp0"
call .venv\Scripts\activate.bat
cd backend
python -m app.cli migrar
echo Funes Fit en http://localhost:8000  (Ctrl+C para parar)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
