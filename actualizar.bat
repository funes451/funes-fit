@echo off
chcp 65001 > nul
cd /d "%~dp0"
call .venv\Scripts\activate.bat
pip install -r backend\requirements.txt
cd frontend
call npm install
call npm run build
cd ..\backend
python -m app.cli migrar
pause
