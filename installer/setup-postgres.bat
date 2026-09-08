@echo off
REM Passwords are read from temporary files, never command-line arguments.
REM %1=bin, %2=database, %3=app user, %4=app password file,
REM %5=postgres password file, %6=exact Windows service name
setlocal DisableDelayedExpansion
set "PG_BIN=%~1"
set "DB_NAME=%~2"
set "DB_USER=%~3"
set "APP_PASSWORD_FILE=%~4"
set "POSTGRES_PASSWORD_FILE=%~5"
set "PG_SERVICE=%~6"
set "PG_HOST=127.0.0.1"
set "PG_PORT=5432"
set "PSQL=%PG_BIN%\psql.exe"
set "PG_ISREADY=%PG_BIN%\pg_isready.exe"
if not defined PG_BIN (echo ERROR: PostgreSQL bin path not provided& exit /b 10)
if not defined DB_NAME set "DB_NAME=inventory_db"
if not defined DB_USER set "DB_USER=inventory_user"
if not exist "%PSQL%" (echo ERROR: psql.exe was not found& exit /b 11)
if not exist "%PG_ISREADY%" (echo ERROR: pg_isready.exe was not found& exit /b 12)
if not defined PG_SERVICE (echo ERROR: PostgreSQL service name not provided& exit /b 13)
if not exist "%APP_PASSWORD_FILE%" (echo ERROR: Application credential file not found& exit /b 14)
set /p "APP_DB_PASSWORD="<"%APP_PASSWORD_FILE%"
if not defined APP_DB_PASSWORD (echo ERROR: Application database password is empty& exit /b 15)
set "POSTGRES_SUPERUSER_PASSWORD="
if exist "%POSTGRES_PASSWORD_FILE%" set /p "POSTGRES_SUPERUSER_PASSWORD="<"%POSTGRES_PASSWORD_FILE%"

echo [1/6] Validating PostgreSQL service...
sc query "%PG_SERVICE%" >nul 2>&1
if errorlevel 1 (echo ERROR: The detected PostgreSQL Windows service does not exist& goto :fail)
echo Found service: %PG_SERVICE%
echo [2/6] Checking service status...
"%PG_ISREADY%" -h "%PG_HOST%" -p "%PG_PORT%" >nul 2>&1
if not errorlevel 1 goto :service_ready
net start "%PG_SERVICE%" >nul 2>&1
if errorlevel 1 sc start "%PG_SERVICE%" >nul 2>&1
if errorlevel 1 (echo ERROR: PostgreSQL service could not be started& goto :fail)
set /a WAIT_SECONDS=0
:wait_service
"%PG_ISREADY%" -h "%PG_HOST%" -p "%PG_PORT%" >nul 2>&1
if not errorlevel 1 goto :service_ready
if %WAIT_SECONDS% GEQ 120 (echo ERROR: PostgreSQL did not become ready within 120 seconds& goto :fail)
timeout /t 2 /nobreak >nul
set /a WAIT_SECONDS+=2
goto :wait_service

:service_ready
echo [3/6] PostgreSQL is accepting connections on port %PG_PORT%.
if not defined POSTGRES_SUPERUSER_PASSWORD goto :verify_preserved_installation
echo [4/6] Validating authenticated postgres connection...
set "PGPASSWORD=%POSTGRES_SUPERUSER_PASSWORD%"
"%PSQL%" -X -w -h "%PG_HOST%" -p "%PG_PORT%" -U postgres -d postgres -c "SELECT 1;" >nul 2>&1
if errorlevel 1 (echo ERROR_CODE=INVALID_POSTGRES_PASSWORD& goto :fail)
echo PostgreSQL administrator authentication succeeded.
echo [5/6] Ensuring application database exists...
"%PSQL%" -X -w -h "%PG_HOST%" -p "%PG_PORT%" -U postgres -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='%DB_NAME%'" | findstr /x /c:"1" >nul
if not errorlevel 1 goto :database_ready
"%PSQL%" -X -w -h "%PG_HOST%" -p "%PG_PORT%" -U postgres -d postgres -c "CREATE DATABASE %DB_NAME%;"
if errorlevel 1 (echo ERROR: Application database could not be created& goto :fail)
:database_ready
echo [6/6] Ensuring application user exists...
"%PSQL%" -X -w -h "%PG_HOST%" -p "%PG_PORT%" -U postgres -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='%DB_USER%'" | findstr /x /c:"1" >nul
if not errorlevel 1 goto :existing_user
(echo CREATE USER %DB_USER% WITH PASSWORD '%APP_DB_PASSWORD%';) | "%PSQL%" -X -w -h "%PG_HOST%" -p "%PG_PORT%" -U postgres -d postgres
if errorlevel 1 (echo ERROR: Application user could not be created& goto :fail)
goto :grant_permissions
:existing_user
echo Existing application user found; preserving its password.
set "PGPASSWORD=%APP_DB_PASSWORD%"
"%PSQL%" -X -w -h "%PG_HOST%" -p "%PG_PORT%" -U "%DB_USER%" -d "%DB_NAME%" -c "SELECT 1;" >nul 2>&1
if errorlevel 1 (echo ERROR_CODE=APP_CREDENTIALS_MISMATCH& goto :fail)
set "PGPASSWORD=%POSTGRES_SUPERUSER_PASSWORD%"
:grant_permissions
"%PSQL%" -X -w -h "%PG_HOST%" -p "%PG_PORT%" -U postgres -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE %DB_NAME% TO %DB_USER%;" >nul
if errorlevel 1 goto :grant_failed
"%PSQL%" -X -w -h "%PG_HOST%" -p "%PG_PORT%" -U postgres -d "%DB_NAME%" -c "GRANT ALL ON SCHEMA public TO %DB_USER%;" >nul
if errorlevel 1 goto :grant_failed
"%PSQL%" -X -w -h "%PG_HOST%" -p "%PG_PORT%" -U postgres -d "%DB_NAME%" -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO %DB_USER%; ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO %DB_USER%;" >nul
if errorlevel 1 goto :grant_failed
goto :verify_application
:grant_failed
echo ERROR: Application database privileges could not be granted
goto :fail
:verify_preserved_installation
echo [4/6] Validating preserved application credentials...
:verify_application
set "PGPASSWORD=%APP_DB_PASSWORD%"
"%PSQL%" -X -w -h "%PG_HOST%" -p "%PG_PORT%" -U "%DB_USER%" -d "%DB_NAME%" -c "SELECT 1;" >nul 2>&1
if errorlevel 1 (echo ERROR_CODE=APP_CREDENTIALS_MISMATCH& goto :fail)
echo Application database connection succeeded.
set "PGPASSWORD="
set "APP_DB_PASSWORD="
set "POSTGRES_SUPERUSER_PASSWORD="
exit /b 0
:fail
set "PGPASSWORD="
set "APP_DB_PASSWORD="
set "POSTGRES_SUPERUSER_PASSWORD="
exit /b 1
