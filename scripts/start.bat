@echo off
title Sistema de Inventario - Agricola Vita Santa Fe
echo ============================================
echo   Sistema de Inventario - Agricola Vita Santa Fe
echo   Iniciando servidor de produccion...
echo ============================================
echo.

REM Verificar que existe .env
if not exist ".env" (
    echo ERROR: No se encontro el archivo .env
    echo Copie .env.example a .env y configure los valores.
    pause
    exit /b 1
)

REM Verificar que existe el entorno virtual
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: No se encontro el entorno virtual (.venv).
    echo Ejecute: python -m venv .venv
    echo Luego: .venv\Scripts\activate
    echo Luego: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activar entorno virtual
call .venv\Scripts\activate.bat

REM Verificar dependencias criticas
python -c "import flask" 2>nul
if errorlevel 1 (
    echo ERROR: Flask no esta instalado.
    echo Ejecute: pip install -r requirements.txt
    pause
    exit /b 1
)

python -c "import waitress" 2>nul
if errorlevel 1 (
    echo ERROR: Waitress no esta instalado.
    echo Ejecute: pip install waitress
    pause
    exit /b 1
)

python -c "import psycopg" 2>nul
if errorlevel 1 (
    echo ERROR: psycopg no esta instalado.
    echo Ejecute: pip install psycopg
    pause
    exit /b 1
)

echo Verificando conexion a PostgreSQL...
python -c "from app import _check_postgres; from config import Config; ok, msg = _check_postgres(Config.SQLALCHEMY_DATABASE_URI); print(f'Estado: {msg}'); exit(0 if ok else 1)"
if errorlevel 1 (
    echo.
    echo ERROR: No se pudo conectar a PostgreSQL.
    echo Verifique que el servicio este corriendo y que DATABASE_URL sea correcto.
    echo Revise el archivo .env.
    pause
    exit /b 1
)

echo.
echo Iniciando servidor en http://0.0.0.0:5000
echo Presione Ctrl+C para detener.
echo.

python production.py

pause
