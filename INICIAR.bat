@echo off
rem Enciende SuperMath con doble clic. La primera vez se prepara solo (necesita internet).
cd /d "%~dp0"
title SuperMath - NO CIERRE ESTA VENTANA MIENTRAS USA EL PROGRAMA

rem 1. Buscar Python
set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY ( py -3 --version >nul 2>&1 && set "PY=py -3" )
if not defined PY (
    echo.
    echo  NO SE ENCONTRO PYTHON EN ESTE COMPUTADOR.
    echo  Siga el PASO 2 del manual para instalarlo y luego haga doble clic en INICIAR otra vez.
    echo.
    pause
    exit /b 1
)

rem 2. Si la carpeta .venv viene de otro computador, no sirve: se borra y se rehace
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" --version >nul 2>&1 || rmdir /s /q ".venv"
)

rem 3. Primera vez: preparar el programa
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo  Preparando SuperMath por primera vez. Puede tardar varios minutos. Espere...
    echo.
    %PY% -m venv .venv
    if errorlevel 1 goto error
)
if not exist ".venv\listo.txt" (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto error
    echo listo> ".venv\listo.txt"
)

rem 4. Abrir el navegador unos segundos despues y encender el programa
start "" cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:5000"
echo.
echo  SuperMath esta encendido. Se abrira el navegador solo.
echo  Si no se abre, escriba en el navegador:  127.0.0.1:5000
echo  Para APAGAR el programa, cierre esta ventana.
echo.
".venv\Scripts\python.exe" app.py
echo.
echo  SuperMath se detuvo. Si fue un error, lea el texto de arriba.
pause
exit /b 0

:error
echo.
echo  OCURRIO UN ERROR durante la preparacion. Revise que tenga internet y haga doble clic en INICIAR otra vez.
echo.
pause
exit /b 1
