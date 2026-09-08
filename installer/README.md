# Instalador - Inventory System

## Requisitos del sistema

- Windows 10 o superior (64-bit)
- PostgreSQL 14+ (se detecta o instala automaticamente)
- No requiere Python ni .venv

## Construir el instalador

### 1. Pre-requisitos

1. Instalar [Inno Setup 6+](https://jrsoftware.org/isdl.php)
2. Ejecutar `scripts\build.bat` para generar `dist\inventory-system.exe`

### 2. PostgreSQL (opcional pero recomendado)

Para automatizar la instalacion de PostgreSQL:

1. Descargar el instalador offline de PostgreSQL desde:
   https://www.postgresql.org/download/windows/
2. Renombrar el archivo a `postgresql-installer.exe`
3. Colocarlo en la carpeta `installer\`
4. El instalador lo ejecutara automaticamente si PostgreSQL no esta instalado

**Nota**: El instalador de PostgreSQL NO se sube al repositorio por tamano.
Consulte `installer\README.md` para instrucciones detalladas.

### 3. Construir

```
scripts\build-installer.bat
```

El instalador se genera en `installer\output\InventorySystemSetup.exe`.

## Flujo de instalacion

### Instalacion limpia (sin PostgreSQL)

1. El instalador detecta que PostgreSQL no esta instalado
2. Pregunta si desea continuar (puede instalar PostgreSQL despues)
3. Instala la aplicacion y archivos necesarios
4. Crea accesos directos
5. Al iniciar, muestra el asistente de configuracion
6. El usuario configura: contrasena admin, puerto, zona horaria, SMTP

### Instalacion limpia (con PostgreSQL detectado)

1. El instalador detecta PostgreSQL automaticamente
2. Crea la base de datos `inventory_db`
3. Crea el usuario `inventory_user` con credenciales seguras
4. Genera `.env` con `DATABASE_URL` y `SECRET_KEY`
5. Instala la aplicacion
6. Al iniciar, muestra el asistente de configuracion

### Actualizacion

1. Ejecutar el nuevo instalador sobre la instalacion existente
2. El instalador preserva: `.env`, `logs/`, `backups/`
3. Los accesos directos se actualizan
4. La base de datos NO se ve afectada

### Desinstalacion

1. Panel de control > Programas > Inventory System > Desinstalar
2. O desde el grupo de Inicio > Desinstalar Inventory System
3. **Se conservan**: base de datos, respaldos, configuracion `.env`
4. **Se eliminan**: ejecutable, logs, archivos temporales
5. Para eliminar la base de datos, hacerlo manualmente

## PostgreSQL

### Deteccion automatica

El instalador busca PostgreSQL en:
1. Registro de Windows: `HKLM\SOFTWARE\PostgreSQL\Installations\`
2. Rutas por defecto: `C:\Program Files\PostgreSQL\14-17\`

### Configuracion automatica

Cuando detecta PostgreSQL, el instalador:
1. Verifica que el servicio este corriendo
2. Crea la base de datos `inventory_db`
3. Crea el usuario `inventory_user`
4. Genera contrasena aleatoria de 20 caracteres
5. Otorga privilegios completos
6. Configura `pg_hba.conf` para conexiones locales

### Credenciales

- **Usuario de BD**: `inventory_user`
- **Contrasena**: Generada aleatoriamente (20 caracteres)
- **Base de datos**: `inventory_db`
- Las credenciales se guardan en `.env` (no versionado)
- **NUNCA** se muestran en la interfaz del instalador

### PostgreSQL manual (si no se detecta)

Si el instalador no detecta PostgreSQL:

1. Instalar PostgreSQL 14+ desde https://www.postgresql.org/download/windows/
2. Durante la instalacion:
   - Puerto: 5432 (default)
   - Contraseña del usuario `postgres`: elegir una segura
   - Locale: `Spanish - Mexico` o `en_US.UTF-8`
3. Abrir pgAdmin y ejecutar:

```sql
CREATE DATABASE inventory_db;
CREATE USER inventory_user WITH PASSWORD 'su_contrasena';
GRANT ALL PRIVILEGES ON DATABASE inventory_db TO inventory_user;
\c inventory_db
GRANT ALL ON SCHEMA public TO inventory_user;
```

4. Configurar `.env` con:

```
DATABASE_URL=postgresql+psycopg://inventory_user:su_contrasena@localhost:5432/inventory_db
```

## Asistente de primera ejecucion

Al iniciar por primera vez, la aplicacion detecta que falta configuracion
y muestra el asistente en el navegador. El usuario configura:

1. **Contrasena del administrador**: para acceder al panel de control
2. **Puerto**: default 5000
3. **Acceso**: local (127.0.0.1) o red (0.0.0.0)
4. **Zona horaria**: America/Chihuahua (default)
5. **Correo SMTP** (opcional): para envio de reportes

La configuracion se guarda en `.env`. El usuario debe reiniciar la aplicacion.

## Archivos incluidos

- `inventory-system.exe` - Ejecutable windowed (sin consola)
- `.env.example` - Plantilla de configuracion
- `static/img/branding/` - Logos y iconos
- `migrations/` - Migraciones de base de datos
- `installer/` - Scripts de configuracion de PostgreSQL

## Archivos NO incluidos

- `.env` con credenciales reales
- Base de datos
- Respaldos
- Python ni .venv
- Instalador de PostgreSQL (ver instrucciones arriba)
