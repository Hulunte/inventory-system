@echo off
echo ============================================
echo   Construccion del Ejecutable
echo   Sistema de Inventario
echo ============================================
echo.

REM Verificar entorno virtual
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: No se encontro el entorno virtual (.venv).
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

REM Verificar PyInstaller
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Instalando PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: No se pudo instalar PyInstaller.
        pause
        exit /b 1
    )
)

echo Construyendo ejecutable...
echo Esto puede tardar varios minutos.
echo.

REM Remove complete previous outputs so a failed build cannot leave a stale EXE.
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

python build_wrapper.py build.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo ERROR: La construccion fallo.
) else (
    echo.
    echo Construccion completada.
    echo El ejecutable se encuentra en: dist\inventory-system.exe
)

pause
