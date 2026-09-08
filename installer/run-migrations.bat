@echo off
REM Run Flask database migrations for Inventory System
REM Called by Inno Setup after PostgreSQL setup
REM Note: This script runs migrations using the bundled Flask CLI.
REM If flask is not available, migrations will run on first app start.

setlocal enabledelayedexpansion

set "APP_DIR=%~1"

if "%APP_DIR%"=="" (
    echo ERROR: Application directory not provided
    exit /b 1
)

echo.
echo ==========================================
echo   Running Database Migrations
echo ==========================================
echo.

cd /d "%APP_DIR%"

REM The exe bundles Flask and Alembic. Migrations run automatically
REM when the application starts via Flask-Migrate.
REM This script is a placeholder for future manual migration needs.

echo Migration note: Database migrations run automatically when the
echo application starts for the first time via Flask-Migrate.
echo.
echo No manual migration needed at this time.
echo.
echo ==========================================
echo   Migration check complete
echo ==========================================
exit /b 0
