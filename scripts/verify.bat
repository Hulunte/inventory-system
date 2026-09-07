@echo off
echo ============================================
echo   Verificacion del Entorno
echo   Sistema de Inventario
echo ============================================
echo.

set ERRORS=0

REM 1. Python
echo [1/7] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo   FAIL: Python no encontrado en PATH.
    echo   Instale Python 3.10+ desde https://python.org
    set /a ERRORS+=1
) else (
    python -c "import sys; v=sys.version_info; print(f'  OK: Python {v.major}.{v.minor}.{v.micro}')"
)

REM 2. Entorno virtual
echo.
echo [2/7] Verificando entorno virtual...
if not exist ".venv\Scripts\activate.bat" (
    echo   FAIL: No se encontro .venv
    echo   Ejecute: python -m venv .venv
    set /a ERRORS+=1
) else (
    echo   OK: .venv encontrado
)

REM 3. Dependencias criticas
echo.
echo [3/7] Verificando dependencias criticas...
call .venv\Scripts\activate.bat 2>nul

python -c "import flask; print(f'  OK: Flask {flask.__version__}')" 2>nul
if errorlevel 1 (
    echo   FAIL: Flask no instalado
    set /a ERRORS+=1
)

python -c "import sqlalchemy; print(f'  OK: SQLAlchemy {sqlalchemy.__version__}')" 2>nul
if errorlevel 1 (
    echo   FAIL: SQLAlchemy no instalado
    set /a ERRORS+=1
)

python -c "import psycopg; print(f'  OK: psycopg {psycopg.__version__}')" 2>nul
if errorlevel 1 (
    echo   FAIL: psycopg no instalado
    set /a ERRORS+=1
)

python -c "import waitress; print('  OK: Waitress disponible')" 2>nul
if errorlevel 1 (
    echo   FAIL: Waitress no instalado
    set /a ERRORS+=1
)

python -c "import serial; print(f'  OK: pyserial {serial.__version__}')" 2>nul
if errorlevel 1 (
    echo   WARN: pyserial no instalado (requerido para bascula)
    echo   Instale con: pip install pyserial
)

python -c "import openpyxl; print(f'  OK: openpyxl {openpyxl.__version__}')" 2>nul
if errorlevel 1 (
    echo   WARN: openpyxl no instalado (requerido para exportar Excel)
    echo   Instale con: pip install openpyxl
)

REM 4. Archivo .env
echo.
echo [4/7] Verificando configuracion...
if not exist ".env" (
    echo   FAIL: No se encontro .env
    echo   Copie .env.example a .env y configure los valores.
    set /a ERRORS+=1
) else (
    echo   OK: .env encontrado
)

REM 5. PostgreSQL connection
echo.
echo [5/7] Verificando conexion a PostgreSQL...
python -c "from app import _check_postgres; from config import Config; ok, msg = _check_postgres(Config.SQLALCHEMY_DATABASE_URI); print(f'  {\"OK\" if ok else \"FAIL\"}: {msg}'); exit(0 if ok else 1)" 2>nul
if errorlevel 1 (
    echo   FAIL: No se pudo conectar a PostgreSQL
    set /a ERRORS+=1
)

REM 6. Puertos seriales (pyserial)
echo.
echo [6/7] Verificando puertos seriales (bascula)...
python -c "import serial.tools.list_ports; ports = list(serial.tools.list_ports.comports()); print(f'  OK: {len(ports)} puerto(s) serial encontrado(s)') if ports else print('  INFO: Sin puertos seriales (bascula no conectada - normal)')" 2>nul
if errorlevel 1 (
    echo   INFO: pyserial no disponible o sin puertos seriales
    echo   La bascula no estara disponible hasta conectar un dispositivo.
)

REM 7. Health check
echo.
echo [7/7] Verificando health check...
python -c "from app import create_app; app = create_app(); client = app.test_client(); r = client.get('/api/health'); print(f'  OK: Health check responded {r.status_code}') if r.status_code in (200, 503) else print(f'  FAIL: Unexpected status {r.status_code}')" 2>nul
if errorlevel 1 (
    echo   FAIL: Health check no respondio correctamente
    set /a ERRORS+=1
)

echo.
echo ============================================
if %ERRORS%==0 (
    echo   RESULTADO: Todo esta configurado correctamente.
    echo   Ejecute scripts\start.bat para iniciar.
) else (
    echo   RESULTADO: Se encontraron %ERRORS% error(es).
    echo   Corrija los problemas antes de iniciar.
)
echo ============================================
echo.

pause
