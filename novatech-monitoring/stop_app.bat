@echo off
REM ============================================================
REM NOVA TECH - Detener la aplicacion
REM
REM Cierra las ventanas que abrio start_app.bat (backend, simulador y
REM frontend). Como respaldo (por ejemplo con Windows Terminal, donde los
REM titulos de ventana no siempre se pueden consultar) detiene:
REM   - lo que escuche en 8080 o 5173, solo si es java.exe o node.exe;
REM   - el Python del simulador de esta carpeta (simulator\.venv).
REM
REM   stop_app.bat          pide una tecla al terminar
REM   stop_app.bat nopause  sin pausa (lo usa reset_demo.bat)
REM ============================================================
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"

echo.
echo Deteniendo NOVA TECH...

call :close_window "NOVA TECH - Simulador" "Simulador"
call :close_window "NOVA TECH - Frontend" "Frontend"
call :close_window "NOVA TECH - Backend" "Backend"

REM Procesos que hayan quedado escuchando en los puertos de la aplicacion.
call :stop_port 8080 java.exe
call :stop_port 5173 node.exe
call :stop_simulator

echo.
echo NOVA TECH quedo detenida.
if /i not "%~1"=="nopause" (
    echo.
    pause
)
endlocal & exit /b 0

REM ------------------------------------------------------------
REM :close_window "TITULO" "NOMBRE"
REM Mientras corre un comando, cmd agrega " - comando" al titulo; por eso
REM se busca con comodin. /T cierra tambien java, python o node.
REM ------------------------------------------------------------
:close_window
tasklist /v /fi "imagename eq cmd.exe" /fo csv 2>nul | findstr /i /c:"%~1" >nul
if errorlevel 1 (
    echo   %~2: no estaba en ejecucion
    exit /b 0
)
taskkill /fi "windowtitle eq %~1*" /t /f >nul 2>nul
echo   %~2: detenido
exit /b 0

REM ------------------------------------------------------------
REM :stop_port PUERTO PROGRAMA
REM ------------------------------------------------------------
:stop_port
for /f "tokens=5" %%p in ('netstat -ano -p TCP ^| findstr /c:":%~1 " ^| findstr /c:"LISTENING"') do (
    tasklist /fi "pid eq %%p" /fo csv /nh 2>nul | findstr /i /c:"%~2" >nul
    if not errorlevel 1 (
        taskkill /pid %%p /t /f >nul 2>nul
        echo   Puerto %~1: se detuvo %~2 ^(PID %%p^)
    )
)
exit /b 0

REM ------------------------------------------------------------
REM :stop_simulator  -> procesos python.exe de simulator\.venv de esta carpeta
REM ------------------------------------------------------------
:stop_simulator
set "NT_VENV=%ROOT%simulator\.venv\"
for /f %%p in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.ExecutablePath -like ($env:NT_VENV + '*') } | ForEach-Object { $_.ProcessId }" 2^>nul') do (
    taskkill /pid %%p /t /f >nul 2>nul
    echo   Simulador: se detuvo python.exe ^(PID %%p^)
)
exit /b 0
