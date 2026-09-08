@echo off
echo ============================================
echo   Construccion del Instalador
echo   Inventory System
echo ============================================
echo.

REM Verify exe exists
if not exist "dist\inventory-system.exe" (
    echo ERROR: No se encontro dist\inventory-system.exe
    echo Ejecute primero: scripts\build.bat
    pause
    exit /b 1
)

REM Find ISCC.exe
set "ISCC="
where iscc >nul 2>&1
if !errorlevel! equ 0 (
    set "ISCC=iscc"
    goto :found
)

REM Check winget install location
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" goto :found

REM Check Program Files locations
set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" goto :found

set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" goto :found

echo ERROR: Inno Setup no encontrado.
echo Instale Inno Setup 6+ con: winget install JRSoftware.InnoSetup
pause
exit /b 1

:found
echo Using ISCC: %ISCC%
echo.

REM Remove the previous installer so success can never report a stale artifact.
if exist "installer\output\InventorySystemSetup.exe" del /f /q "installer\output\InventorySystemSetup.exe"

"%ISCC%" "installer\inventory-system.iss"

if errorlevel 1 (
    echo.
    echo ERROR: La construccion del instalador fallo.
) else (
    echo.
    echo Instalador construido exitosamente.
    echo Ubicacion: installer\output\InventorySystemSetup.exe
)

pause
