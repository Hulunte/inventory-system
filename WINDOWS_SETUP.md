# Instalacion en Windows - Sistema de Inventario

Guia para instalar y ejecutar el sistema de inventario en una laptop Windows.

## Requisitos previos

- Windows 10 o 11 (64-bit)
- Python 3.10 o superior
- PostgreSQL 14 o superior
- Conexion a la red local (para acceso desde otros dispositivos)

## 1. Instalar Python

1. Descargar Python 3.10+ desde https://python.org/downloads
2. Durante la instalacion, marcar **"Add Python to PATH"**
3. Verificar la instalacion:
   ```
   python --version
   ```

## 2. Instalar PostgreSQL

1. Descargar PostgreSQL desde https://www.postgresql.org/download/windows/
2. Durante la instalacion, recordar la contraseña del usuario `postgres`
3. Crear la base de datos:
   ```
   psql -U postgres
   CREATE DATABASE inventory_db;
   CREATE DATABASE inventory_test_db;
   \q
   ```

## 3. Configurar el proyecto

### Copiar archivos del proyecto

Copiar la carpeta del proyecto a la ubicacion deseada, por ejemplo:
```
C:\inventory-system
```

### Crear entorno virtual

```cmd
cd C:\inventory-system
python -m venv .venv
.venv\Scripts\activate
```

### Instalar dependencias

```cmd
pip install -r requirements.txt
```

### Configurar el archivo .env

```cmd
copy .env.example .env
```

Editar `.env` con un editor de texto (como Notepad) y configurar:

| Variable | Descripcion | Ejemplo |
|---|---|---|
| `DATABASE_URL` | URL de conexion a PostgreSQL | `postgresql+psycopg://postgres:mi_password@localhost:5432/inventory_db` |
| `TEST_DATABASE_URL` | URL de la base de datos de pruebas | `postgresql+psycopg://postgres:mi_password@localhost:5432/inventory_test_db` |
| `SECRET_KEY` | Clave secreta (minimo 16 caracteres) | `mi-clave-secreta-super-larga` |
| `ADMIN_PASSWORD_HASH` | Hash de la contraseña de administrador | Generar con: `python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('su_password'))"` |
| `HARVEST_TIMEZONE` | Zona horaria | `America/Chihuahua` |
| `BACKUP_DIR` | Carpeta para respaldos | `C:\backups\inventory-system` |
| `APP_HOST` | Host del servidor | `0.0.0.0` |
| `APP_PORT` | Puerto del servidor | `5000` |

**IMPORTANTE**: Nunca compartir el archivo `.env` ni subirlo a repositorios.

## 4. Verificar la instalacion

```cmd
scripts\verify.bat
```

Este script verificara:
- Python y version
- Entorno virtual
- Dependencias criticas
- Archivo .env
- Conexion a PostgreSQL
- Puertos seriales (bascula)
- Health check de la aplicacion

## 5. Iniciar la aplicacion

```cmd
scripts\start.bat
```

La aplicacion estara disponible en: `http://localhost:5000`

## 6. Acceso desde otra computadora o celular

### Configuracion de red

1. El servidor escucha en `0.0.0.0:5000` (todas las interfaces de red)
2. Verificar la IP de la laptop:
   ```
   ipconfig
   ```
   Buscar la direccion IPv4 (ejemplo: `192.168.1.100`)

3. Desde otro dispositivo en la misma red, acceder a:
   ```
   http://192.168.1.100:5000
   ```

### Firewall de Windows

Si otros dispositivos no pueden conectarse:

1. Abrir "Firewall de Windows Defender con seguridad avanzada"
2. Crear una regla de entrada:
   - Tipo: Puerto
   - Puerto local: 5000
   - Accion: Permitir la conexion
   - Perfiles: Privado (y Public si es necesario)
   - Nombre: Inventario Flask

## 7. Bascula (pyserial)

### Sin bascula conectada

Si no hay bascula conectada, el sistema funcionara normalmente. En la seccion de bascula aparecera:
- "Sin puertos seriales" o "Bascula no conectada"
- Esto es NORMAL y NO indica un error

### Con bascula conectada

1. Conectar la bascula via USB
2. Instalar el driver del fabricante si Windows no detecta el puerto COM
3. En la pantalla de recepcion, ir a la seccion "Bascula"
4. Seleccionar el puerto COM correcto
5. Hacer clic en "Conectar"

### Verificar puertos seriales

```cmd
python -c "import serial.tools.list_ports; print([p.device for p in serial.tools.list_ports.comports()])"
```

Si no aparece ningun puerto, la bascula no esta conectada o falta el driver.

## 8. Respaldo de base de datos

### Respaldo manual

```cmd
scripts\backup.bat
```

Los respaldos se guardan en la carpeta configurada en `BACKUP_DIR`.

### Respaldo automatico (opcional)

Para programar respaldos diarios en Windows:

1. Abrir "Tareas Programadas"
2. Crear tarea basica:
   - Nombre: Respaldo Inventario
   - Accion: Iniciar programa
   - Programa: `C:\inventory-system\scripts\backup.bat`
   - Horario: Diario a las 23:00

## 9. Solucion de problemas

### "PostgreSQL no esta disponible"

1. Verificar que el servicio de PostgreSQL este corriendo:
   ```
   services.msc
   ```
   Buscar "postgresql" y iniciar si esta detenido.

2. Verificar que `DATABASE_URL` en `.env` sea correcto.

### "SECRET_KEY debe tener al menos 16 caracteres"

Editar `.env` y cambiar `SECRET_KEY` por una clave mas larga.

### "Faltan variables de entorno obligatorias"

Copiar `.env.example` a `.env` y configurar todas las variables.

### La aplicacion no inicia

1. Ejecutar `scripts\verify.bat` para diagnosticar
2. Verificar que todas las dependencias esten instaladas
3. Verificar que PostgreSQL este corriendo

### No se puede acceder desde otro dispositivo

1. Verificar que ambos dispositivos esten en la misma red
2. Verificar la IP de la laptop con `ipconfig`
3. Verificar que el firewall permita el puerto 5000
4. Probar desde la misma laptop: `http://localhost:5000`

## 10. Archivos importantes

| Archivo | Descripcion |
|---|---|
| `production.py` | Punto de entrada para produccion |
| `run.py` | Punto de entrada para desarrollo (NO usar en produccion) |
| `config.py` | Configuracion de la aplicacion |
| `.env` | Variables de entorno (NO compartir) |
| `.env.example` | Plantilla de variables de entorno |
| `requirements.txt` | Dependencias de Python |
| `scripts/start.bat` | Script de inicio |
| `scripts/verify.bat` | Script de verificacion |
| `scripts/backup.bat` | Script de respaldo |
| `build.spec` | Spec para PyInstaller (futuro instalador) |
