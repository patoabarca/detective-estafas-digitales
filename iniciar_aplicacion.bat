@echo off
setlocal EnableExtensions
title Detective de Estafas Digitales - Mini App Web
cd /d "%~dp0"

set "VENV_DIR=.venv"

rem --- Windows limita las rutas a 260 caracteres y algunos paquetes (streamlit)
rem --- traen archivos de mas de 150 caracteres de ruta relativa. Si la carpeta del
rem --- proyecto es larga, el venv se crea en una ubicacion corta fuera del proyecto.
set "PROJECT_DIR=%CD%"
if not "%PROJECT_DIR:~80,1%"=="" set "VENV_DIR=%LOCALAPPDATA%\DetectiveEstafasDigitales\venv"

set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "REQ_FILE=requirements-web.txt"
set "REQ_COPY=%VENV_DIR%\requirements-web.installed"
set "IMPORT_CHECK=import streamlit, PIL, pytesseract, reportlab, docx, pptx"
set "REBUILT=0"

echo ===================================================
echo   INICIANDO DETECTIVE DE ESTAFAS DIGITALES
echo ===================================================
echo.

if not exist "%REQ_FILE%" (
    echo [ERROR] No se encontro %REQ_FILE% en esta carpeta.
    goto :fail
)

echo [1/3] Verificando el entorno virtual en: %VENV_DIR%

rem --- El interprete del venv debe poder ejecutarse. Si el .venv se copio de
rem --- otra PC, python.exe apunta a una instalacion que ya no existe.
if not exist "%VENV_PY%" (
    echo       No existe un entorno virtual.
    goto :rebuild
)
"%VENV_PY%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 (
    echo       El entorno virtual es invalido: su Python base no existe o no es compatible.
    goto :rebuild
)

:check_deps
"%VENV_PY%" -c "%IMPORT_CHECK%" >nul 2>&1
if errorlevel 1 (
    echo       Faltan dependencias en el entorno virtual.
    goto :install
)
rem --- Dependencias presentes: reinstalar solo si cambio requirements-web.txt.
if not exist "%REQ_COPY%" goto :install
fc /b "%REQ_FILE%" "%REQ_COPY%" >nul 2>&1
if errorlevel 1 (
    echo       requirements-web.txt cambio desde la ultima instalacion.
    goto :install
)
echo       Entorno virtual valido.
goto :launch

:rebuild
if "%REBUILT%"=="1" (
    echo [ERROR] No se pudo dejar el entorno virtual en estado funcional.
    goto :fail
)
set "REBUILT=1"
echo [2/3] Reconstruyendo el entorno virtual...

call :find_python
if errorlevel 1 (
    echo [ERROR] No se encontro Python 3.9 o superior instalado.
    echo         Instalalo desde https://www.python.org/downloads/ marcando "Add python.exe to PATH".
    goto :fail
)

if exist "%VENV_DIR%" (
    echo       Eliminando el entorno virtual anterior...
    rmdir /s /q "%VENV_DIR%"
    if exist "%VENV_DIR%" (
        echo [ERROR] No se pudo eliminar la carpeta %VENV_DIR%. Cerra los programas que la usen e intenta de nuevo.
        goto :fail
    )
)

echo       Creando entorno virtual con: %PY_CMD%
%PY_CMD% -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo [ERROR] Fallo la creacion del entorno virtual.
    goto :fail
)

:install
echo [2/3] Instalando dependencias de %REQ_FILE% ...
"%VENV_PY%" -m pip install --disable-pip-version-check -r "%REQ_FILE%"
if errorlevel 1 (
    echo       Fallo la instalacion de dependencias.
    goto :rebuild
)
"%VENV_PY%" -c "%IMPORT_CHECK%" >nul 2>&1
if errorlevel 1 (
    echo       Las dependencias instaladas no se pueden importar.
    goto :rebuild
)
copy /y "%REQ_FILE%" "%REQ_COPY%" >nul
echo       Dependencias instaladas correctamente.

:launch
echo [3/3] Abriendo la aplicacion web en tu navegador...
echo       Para cerrar la aplicacion, presiona Ctrl + C en esta ventana.
echo.

rem --- "python -m streamlit" evita depender de streamlit.exe, cuyo lanzador
rem --- guarda la ruta absoluta del Python con el que se creo el entorno.
"%VENV_PY%" -m streamlit run app.py
goto :end

:find_python
set "PY_CMD="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3"
    exit /b 0
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=python"
    exit /b 0
)
exit /b 1

:fail
echo.
echo La aplicacion no pudo iniciarse.

:end
pause
endlocal
