@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo Instalando Funes Fit...
py -3 -m venv .venv || python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r backend\requirements.txt || goto error
if not exist backend\.env copy backend\.env.ejemplo backend\.env
cd frontend
call npm install || goto error
call npm run build || goto error
cd ..\backend
python -m app.cli migrar || goto error
echo.
echo Listo. Crea tu cuenta con:
echo   .venv\Scripts\activate
echo   cd backend
echo   python -m app.cli crear-cuenta --email TU_CORREO --plan funes
echo Y arranca con iniciar.bat
pause
exit /b 0
:error
echo Ha fallado la instalacion. Revisa el mensaje de arriba.
pause
exit /b 1
