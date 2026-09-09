@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "APP_DIR=%%~fI"
set "ENV_FILE=%APP_DIR%\.env"

echo ============================================
echo   Respaldo de Base de Datos
echo   Sistema de Inventario
echo ============================================
echo.

if not exist "%ENV_FILE%" (
    echo ERROR: No se encontro el archivo .env en "%ENV_FILE%".
    exit /b 2
)

if exist "%APP_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%APP_DIR%\.venv\Scripts\python.exe"
) else (
    where python.exe >nul 2>&1
    if errorlevel 1 (
        echo ERROR: No se encontro Python para ejecutar el respaldo.
        exit /b 3
    )
    set "PYTHON_EXE=python.exe"
)

"%PYTHON_EXE%" "%SCRIPT_DIR%backup.py" --env-file "%ENV_FILE%"
set "BACKUP_EXIT_CODE=%ERRORLEVEL%"
if not "%BACKUP_EXIT_CODE%"=="0" (
    echo.
    echo ERROR: El respaldo fallo con codigo %BACKUP_EXIT_CODE%.
    exit /b %BACKUP_EXIT_CODE%
)

echo.
echo Respaldo completado exitosamente.
exit /b 0
