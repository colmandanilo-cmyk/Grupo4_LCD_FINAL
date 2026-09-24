@echo off
REM ============================================================
REM NOVA TECH - Pruebas automaticas
REM
REM   run_tests.bat         pruebas del backend (JUnit) y del simulador (unittest)
REM   run_tests.bat demo    ademas recorre el escenario de demostracion completo
REM                         por API (requiere backend y simulador en marcha)
REM
REM Las pruebas del backend usan su propia base de datos en
REM backend\target\test-data\ y no modifican backend\data\novatech.db.
REM ============================================================
setlocal
cd /d "%~dp0"
title NOVA TECH - Pruebas

set "BACKEND_RESULT=NO EJECUTADO"
set "SIMULATOR_RESULT=NO EJECUTADO"
set "DEMO_RESULT=NO SOLICITADO"
set "FAILED=0"
set "PYTHON=%~dp0simulator\.venv\Scripts\python.exe"

echo.
echo ============================================================
echo  NOVA TECH - Pruebas automaticas
echo ============================================================

REM ---------------- 1. Backend Java ----------------
echo.
echo [1/2] Pruebas del backend (JUnit)...
where java >nul 2>nul
if errorlevel 1 (
    echo   No se encontro Java. Instale Java 17 o superior y ejecute install.bat.
    set "BACKEND_RESULT=FALLA (Java no instalado)"
    set "FAILED=1"
    goto simulator
)
pushd backend
call mvnw.cmd -B --no-transfer-progress test
if errorlevel 1 (
    set "BACKEND_RESULT=FALLA"
    set "FAILED=1"
) else (
    set "BACKEND_RESULT=OK"
)
popd

REM ---------------- 2. Simulador Python ----------------
:simulator
echo.
echo [2/2] Pruebas del simulador (unittest)...
if not exist "%PYTHON%" (
    echo   No existe el entorno de Python del simulador. Ejecute install.bat primero.
    set "SIMULATOR_RESULT=FALLA (falta simulator\.venv)"
    set "FAILED=1"
    goto demo
)
pushd simulator
"%PYTHON%" -m unittest discover -s tests -t . -v
if errorlevel 1 (
    set "SIMULATOR_RESULT=FALLA"
    set "FAILED=1"
) else (
    set "SIMULATOR_RESULT=OK"
)
popd

REM ---------------- 3. Escenario de demostracion (opcional) ----------------
:demo
if /i not "%~1"=="demo" goto summary
echo.
echo [extra] Escenario de demostracion completo por API...
if not exist "%PYTHON%" (
    set "DEMO_RESULT=FALLA (falta simulator\.venv)"
    set "FAILED=1"
    goto summary
)
pushd simulator
"%PYTHON%" tests\check_demo_flow.py
if errorlevel 1 (
    set "DEMO_RESULT=FALLA"
    set "FAILED=1"
) else (
    set "DEMO_RESULT=OK"
)
popd

REM ---------------- Resumen ----------------
:summary
echo.
echo ============================================================
echo  Resumen
echo ============================================================
echo   Backend (JUnit) ........... %BACKEND_RESULT%
echo   Simulador (unittest) ...... %SIMULATOR_RESULT%
echo   Escenario de demostracion . %DEMO_RESULT%
if /i not "%~1"=="demo" echo   (Para probar el escenario completo: start_app.bat y luego run_tests.bat demo)
echo.
if "%FAILED%"=="1" (
    echo Hay pruebas con fallas. Revise los mensajes de arriba.
) else (
    echo Todas las pruebas pasaron.
)
echo.
pause
endlocal & exit /b %FAILED%
