@echo off
REM ============================================================
REM NOVA TECH - Iniciar la aplicacion
REM
REM Abre tres ventanas, una por componente:
REM   "NOVA TECH - Backend"    Java + Spring Boot en el puerto 8080
REM   "NOVA TECH - Simulador"  Python, hace de camaras, energia y conectividad
REM   "NOVA TECH - Frontend"   React (Vite) en el puerto 5173
REM y abre el navegador cuando todo responde.
REM Para detener todo: stop_app.bat (o cerrar las tres ventanas).
REM ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title NOVA TECH - Inicio

set "ROOT=%~dp0"
set "VENV_PY=%ROOT%simulator\.venv\Scripts\python.exe"
set "JAR=%ROOT%backend\target\novatech-backend.jar"

echo.
echo ============================================================
echo  NOVA TECH - Sistema de Monitoreo y Vigilancia para Obras
echo ============================================================
echo.

REM ---------------- Verificar la instalacion ----------------
set "MISSING="
if not exist "%JAR%" set "MISSING=backend compilado"
if not exist "%VENV_PY%" set "MISSING=entorno del simulador"
if not exist "%ROOT%frontend\node_modules" set "MISSING=dependencias del frontend"
if defined MISSING (
    echo Falta instalar: !MISSING!.
    echo Ejecute primero install.bat.
    goto fail
)

REM ---------------- Verificar los puertos ----------------
call :port_in_use 8080
if not errorlevel 1 (
    echo El puerto 8080 ya esta en uso.
    echo Si NOVA TECH ya esta abierta, use stop_app.bat y vuelva a intentarlo.
    echo Si es otro programa, cierrelo antes de continuar.
    goto fail
)
call :port_in_use 5173
if not errorlevel 1 (
    echo El puerto 5173 ya esta en uso.
    echo Si NOVA TECH ya esta abierta, use stop_app.bat y vuelva a intentarlo.
    echo Si es otro programa, cierrelo antes de continuar.
    goto fail
)

REM ---------------- 1. Backend ----------------
echo [1/3] Iniciando el backend Java...
if not exist "%ROOT%backend\data\novatech.db" echo   Primera ejecucion: se crea la base de datos con los datos iniciales.
start "NOVA TECH - Backend" /D "%ROOT%backend" cmd /k java -jar target\novatech-backend.jar
call :wait_url http://127.0.0.1:8080/api/health 120
if errorlevel 1 (
    echo   El backend no respondio en 2 minutos. Revise la ventana "NOVA TECH - Backend".
    goto fail
)
echo   OK: backend en http://localhost:8080/api

REM ---------------- 2. Simulador ----------------
echo [2/3] Iniciando el simulador Python...
start "NOVA TECH - Simulador" /D "%ROOT%simulator" cmd /k .venv\Scripts\python.exe main.py
echo   OK: simulador en marcha (ventana "NOVA TECH - Simulador")

REM ---------------- 3. Frontend ----------------
echo [3/3] Iniciando el frontend React...
start "NOVA TECH - Frontend" /D "%ROOT%frontend" cmd /k npm run dev
call :wait_url http://localhost:5173 60
if errorlevel 1 (
    echo   El frontend no respondio en 1 minuto. Revise la ventana "NOVA TECH - Frontend".
    goto fail
)
echo   OK: frontend en http://localhost:5173

start "" http://localhost:5173

echo.
echo ============================================================
echo  NOVA TECH esta en marcha
echo ============================================================
echo.
echo  Frontend (abrir en el navegador):  http://localhost:5173
echo  Backend (API):                     http://localhost:8080/api
echo  Estado del backend:                http://localhost:8080/api/health
echo.
echo  Usuarios de demostracion:
echo    Administrador  admin@novatech.local       Admin123*
echo    Supervisor     supervisor@novatech.local  Supervisor123*
echo    Operador       operador@novatech.local    Operador123*
echo.
echo  Para detener todo: stop_app.bat
echo  Para volver a los datos iniciales: reset_demo.bat
echo.
echo  Esta ventana se puede cerrar; la aplicacion sigue en las otras tres.
echo.
pause
endlocal & exit /b 0

:fail
echo.
pause
endlocal & exit /b 1

REM ------------------------------------------------------------
REM :port_in_use PUERTO  -> errorlevel 0 si hay algo escuchando en el puerto
REM ------------------------------------------------------------
:port_in_use
netstat -ano -p TCP | findstr /c:":%~1 " | findstr /c:"LISTENING" >nul
exit /b %errorlevel%

REM ------------------------------------------------------------
REM :wait_url URL SEGUNDOS  -> errorlevel 0 cuando la URL responde
REM Usa el Python del simulador (sin proxies del sistema).
REM ------------------------------------------------------------
:wait_url
set /a "WAIT_LEFT=%~2 / 2"
:wait_url_loop
"%VENV_PY%" -c "import sys, urllib.request as u; o = u.build_opener(u.ProxyHandler({})); o.open(sys.argv[1], timeout=2); sys.exit(0)" "%~1" >nul 2>nul
if not errorlevel 1 exit /b 0
set /a "WAIT_LEFT-=1"
if !WAIT_LEFT! LEQ 0 exit /b 1
ping -n 3 127.0.0.1 >nul
goto wait_url_loop
