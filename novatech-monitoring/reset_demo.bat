@echo off
REM ============================================================
REM NOVA TECH - Volver al estado inicial de la demostracion
REM
REM 1. Detiene la aplicacion (stop_app.bat).
REM 2. Borra la base de datos SQLite (novatech.db y sus archivos -wal y -shm).
REM 3. La vuelve a crear con los datos iniciales: 4 obras en OPERACION
REM    NORMAL, 12 camaras, usuarios de demostracion, 24 horas de historial
REM    recien generado y la simulacion automatica activa a velocidad x1.
REM 4. Ofrece iniciar la aplicacion.
REM
REM Se pierden las obras, usuarios, alertas e incidencias creadas despues
REM de la instalacion. La configuracion vuelve a sus valores iniciales.
REM ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title NOVA TECH - Reinicio de la demostracion

set "ROOT=%~dp0"
set "DB=%ROOT%backend\data\novatech.db"

echo.
echo ============================================================
echo  NOVA TECH - Volver a los datos iniciales
echo ============================================================
echo.
echo Se borraran todos los datos registrados (alertas, incidencias,
echo historial, obras y usuarios agregados) y se cargaran otra vez
echo los datos de demostracion.
echo.
choice /c SN /m "Desea continuar"
if errorlevel 2 (
    echo Operacion cancelada. No se modifico nada.
    goto end_ok
)

if not exist "%ROOT%backend\target\novatech-backend.jar" (
    echo.
    echo No existe backend\target\novatech-backend.jar. Ejecute primero install.bat.
    goto fail
)

REM ---------------- 1. Detener ----------------
echo.
echo [1/3] Deteniendo la aplicacion...
call "%ROOT%stop_app.bat" nopause
REM Espera breve para que Windows libere el archivo de la base de datos.
ping -n 3 127.0.0.1 >nul

REM ---------------- 2. Borrar la base ----------------
echo.
echo [2/3] Borrando la base de datos...
for %%f in ("%DB%" "%DB%-wal" "%DB%-shm") do (
    if exist "%%~f" del /f /q "%%~f"
)
if exist "%DB%" (
    echo   No se pudo borrar backend\data\novatech.db: otro programa lo esta usando.
    echo   Cierre las ventanas de NOVA TECH y vuelva a intentarlo.
    goto fail
)
echo   OK

REM ---------------- 3. Crear de nuevo con los datos iniciales ----------------
echo.
echo [3/3] Creando la base con los datos iniciales...
pushd "%ROOT%backend"
java -jar target\novatech-backend.jar --novatech.exit-after-init=true --server.port=0
set "INIT_RESULT=!errorlevel!"
popd
if not "!INIT_RESULT!"=="0" (
    echo   No se pudo crear la base de datos. Comando para repetirlo:
    echo     cd backend
    echo     java -jar target\novatech-backend.jar --novatech.exit-after-init=true --server.port=0
    goto fail
)
echo   OK: datos de demostracion cargados

echo.
echo ============================================================
echo  La demostracion volvio a su estado inicial.
echo ============================================================
echo.
choice /c SN /m "Desea iniciar la aplicacion ahora"
if errorlevel 2 goto end_ok
endlocal
call "%~dp0start_app.bat"
exit /b 0

:end_ok
echo.
pause
endlocal & exit /b 0

:fail
echo.
pause
endlocal & exit /b 1
