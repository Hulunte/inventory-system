@echo off
echo ============================================
echo   Respaldo de Base de Datos
echo   Sistema de Inventario
echo ============================================
echo.

REM Verificar que existe .env
if not exist ".env" (
    echo ERROR: No se encontro el archivo .env
    pause
    exit /b 1
)

REM Activar entorno virtual
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo ERROR: No se encontro el entorno virtual (.venv).
    pause
    exit /b 1
)

REM Ejecutar respaldo via Python
echo Creando respaldo...
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

backup_dir = os.getenv('BACKUP_DIR')
if not backup_dir:
    print('ERROR: BACKUP_DIR no esta configurado en .env')
    exit(1)

os.makedirs(backup_dir, exist_ok=True)

import subprocess
from datetime import datetime

db_url = os.getenv('DATABASE_URL', '')
pg_dump = os.getenv('PG_DUMP_PATH', 'pg_dump')

# Extraer info de la URL
# Formato: postgresql+psycopg://user:pass@host:port/dbname
from urllib.parse import urlparse
parsed = urlparse(db_url.replace('psycopg://', 'postgres://'))

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
filename = f'inventory_backup_{timestamp}.sql'
filepath = os.path.join(backup_dir, filename)

print(f'Respaldando {parsed.hostname}:{parsed.port}/{parsed.path[1:]}...')
print(f'Destino: {filepath}')

env = os.environ.copy()
env['PGPASSWORD'] = parsed.password or ''

cmd = [
    pg_dump,
    '-h', parsed.hostname or 'localhost',
    '-p', str(parsed.port or 5432),
    '-U', parsed.username or 'postgres',
    '-d', parsed.path[1:] if parsed.path else 'inventory_db',
    '-f', filepath,
    '--no-owner',
    '--no-privileges',
]

result = subprocess.run(cmd, env=env, capture_output=True, text=True)

if result.returncode == 0:
    size_kb = os.path.getsize(filepath) / 1024
    print(f'Respaldo creado: {filename} ({size_kb:.1f} KB)')
else:
    print(f'ERROR: {result.stderr}')
    exit(1)
"

if errorlevel 1 (
    echo.
    echo El respaldo fallo. Verifique que pg_dump este disponible.
) else (
    echo.
    echo Respaldo completado exitosamente.
)

pause
