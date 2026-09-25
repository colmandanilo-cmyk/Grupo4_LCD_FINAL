@echo off
REM ============================================================
REM NOVA TECH - Instalacion en Windows 10 / 11
REM
REM Verifica Java, Python y Node.js, instala las dependencias del
REM simulador y del frontend, compila el backend y crea la base de
REM datos con los datos iniciales. Se puede ejecutar de nuevo sin
REM problema: lo que ya esta hecho se reutiliza.
REM
REM La primera vez necesita internet (Maven, pip y npm descargan
REM dependencias). Despues, start_app.bat funciona sin conexion.
REM ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title NOVA TECH - Instalacion

set "ROOT=%~dp0"
set "VENV_PY=%ROOT%simulator\.venv\Scripts\python.exe"

echo.
echo ============================================================
echo  NOVA TECH - Sistema de Monitoreo y Vigilancia para Obras
echo  Instalacion
echo ============================================================
echo.

REM ---------------- 1. Java 17 o superior ----------------
echo [1/7] Verificando Java...
where java >nul 2>nul
if errorlevel 1 (
    echo   No se encontro Java.
    echo   Instale Java 17 o superior, por ejemplo Eclipse Temurin:
    echo     https://adoptium.net/es/temurin/releases/
    echo   Marque la opcion "Set JAVA_HOME" y "Add to PATH" durante la instalacion,
    echo   cierre esta ventana y vuelva a ejecutar install.bat.
    goto fail
)
set "JAVA_VERSION="
for /f "tokens=3" %%v in ('java -version 2^>^&1 ^| findstr /i "version"') do set "JAVA_VERSION=%%~v"
for /f "delims=." %%m in ("!JAVA_VERSION!") do set "JAVA_MAJOR=%%m"
if not defined JAVA_MAJOR set "JAVA_MAJOR=0"
if !JAVA_MAJOR! LSS 17 (
    echo   Se encontro Java !JAVA_VERSION!, pero se necesita Java 17 o superior.
    echo   Descargue una version nueva desde https://adoptium.net/es/temurin/releases/
    goto fail
)
echo   OK: Java !JAVA_VERSION!

REM ---------------- 2. Python 3.10 o superior ----------------
echo.
echo [2/7] Verificando Python...
set "PY="
REM "py -3" es el lanzador oficial de Python para Windows. Se prueba primero
REM porque "python" puede ser el acceso directo de Microsoft Store.
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    echo   No se encontro Python 3.10 o superior.
    echo   Instalelo desde https://www.python.org/downloads/windows/
    echo   y marque "Add python.exe to PATH" en la primera pantalla del instalador.
    goto fail
)
for /f "tokens=2" %%v in ('!PY! --version 2^>^&1') do set "PY_VERSION=%%v"
echo   OK: Python !PY_VERSION! (comando: !PY!)

REM ---------------- 3. Node.js 20.19 o superior ----------------
echo.
echo [3/7] Verificando Node.js...
where node >nul 2>nul
if errorlevel 1 (
    echo   No se encontro Node.js.
    echo   Instale la version LTS desde https://nodejs.org/es/download
    echo   y vuelva a ejecutar install.bat en una ventana nueva.
    goto fail
)
node -e "const [a,b]=process.versions.node.split('.').map(Number); process.exit((a===20&&b>=19)||(a===22&&b>=12)||a>=23?0:1)" >nul 2>nul
if errorlevel 1 (
    for /f %%v in ('node -v') do echo   Se encontro Node.js %%v, pero se necesita 20.19 o superior ^(o 22.12 o superior^).
    echo   Instale la version LTS desde https://nodejs.org/es/download
    goto fail
)
for /f %%v in ('node -v') do echo   OK: Node.js %%v

REM ---------------- 4. Dependencias del simulador ----------------
echo.
echo [4/7] Preparando el simulador Python (simulator\.venv)...
if not exist "%VENV_PY%" (
    !PY! -m venv "%ROOT%simulator\.venv"
    if errorlevel 1 (
        echo   No se pudo crear el entorno virtual. Comando para repetirlo:
        echo     cd simulator
        echo     !PY! -m venv .venv
        goto fail
    )
)
"%VENV_PY%" -m pip install --disable-pip-version-check -q -r "%ROOT%simulator\requirements.txt"
if errorlevel 1 (
    echo   No se pudieron instalar las dependencias de Python. Comando para repetirlo:
    echo     cd simulator
    echo     .venv\Scripts\python -m pip install -r requirements.txt
    goto fail
)
echo   OK: dependencias del simulador instaladas

REM ---------------- 5. Dependencias del frontend ----------------
echo.
echo [5/7] Instalando dependencias del frontend (npm install, puede tardar unos minutos)...
pushd "%ROOT%frontend"
call npm install --no-audit --no-fund
set "NPM_RESULT=!errorlevel!"
popd
if not "!NPM_RESULT!"=="0" (
    echo   Fallo npm install. Comando para repetirlo:
    echo     cd frontend
    echo     npm install
    goto fail
)
echo   OK: dependencias del frontend instaladas

REM ---------------- 6. Compilacion del backend ----------------
echo.
echo [6/7] Compilando el backend Java (la primera vez descarga Maven y las librerias)...
pushd "%ROOT%backend"
call mvnw.cmd -B --no-transfer-progress -q -DskipTests package
set "MVN_RESULT=!errorlevel!"
popd
if not "!MVN_RESULT!"=="0" (
    echo   Fallo la compilacion del backend. Comando para repetirlo:
    echo     cd backend
    echo     mvnw.cmd -DskipTests package
    goto fail
)
if not exist "%ROOT%backend\target\novatech-backend.jar" (
    echo   No se genero backend\target\novatech-backend.jar.
    goto fail
)
echo   OK: backend\target\novatech-backend.jar

REM ---------------- 7. Base de datos y datos iniciales ----------------
echo.
echo [7/7] Base de datos SQLite...
if exist "%ROOT%backend\data\novatech.db" (
    echo   Ya existe backend\data\novatech.db y se conserva.
    echo   Para volver a los datos iniciales use reset_demo.bat.
) else (
    pushd "%ROOT%backend"
    REM server.port=0: usa un puerto libre cualquiera mientras prepara la base.
    java -jar target\novatech-backend.jar --novatech.exit-after-init=true --server.port=0
    set "DB_RESULT=!errorlevel!"
    popd
    if not "!DB_RESULT!"=="0" (
        echo   No se pudo crear la base de datos. Comando para repetirlo:
        echo     cd backend
        echo     java -jar target\novatech-backend.jar --novatech.exit-after-init=true --server.port=0
        goto fail
    )
    echo   OK: base creada con 4 obras, 12 camaras, usuarios y 24 horas de historial
)

echo.
echo ============================================================
echo  Instalacion completa.
echo.
echo  Siguiente paso: ejecute start_app.bat
echo ============================================================
echo.
pause
endlocal & exit /b 0

:fail
echo.
echo ============================================================
echo  La instalacion no termino. Corrija lo indicado arriba y
echo  vuelva a ejecutar install.bat.
echo ============================================================
echo.
pause
endlocal & exit /b 1
