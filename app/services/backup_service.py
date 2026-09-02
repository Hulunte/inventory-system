import glob
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from uuid import uuid4

from flask import current_app
from sqlalchemy.engine import make_url

_BACKUP_PREFIX = "inventory_backup_"
_BACKUP_SUFFIX = ".dump"
_BACKUP_PATTERN = f"{_BACKUP_PREFIX}*{_BACKUP_SUFFIX}"
_BACKUP_NAME_RE = re.compile(
    r"^inventory_backup_\d{4}-\d{2}-\d{2}_\d{6}_\d{6}\.dump$"
)
_BACKUP_DATETIME_FORMAT = "%Y-%m-%d_%H%M%S_%f"
_PG_DUMP_TIMEOUT = 300

_backup_lock = None


def _get_lock():
    global _backup_lock
    if _backup_lock is None:
        import threading
        _backup_lock = threading.Lock()
    return _backup_lock


def _valid_backup_filename(filename):
    if not _BACKUP_NAME_RE.match(filename):
        return False
    datetime_part = filename[len(_BACKUP_PREFIX):-len(_BACKUP_SUFFIX)]
    try:
        datetime.strptime(datetime_part, _BACKUP_DATETIME_FORMAT)
    except ValueError:
        return False
    return True


def _validate_backup_dir():
    backup_dir = current_app.config.get("BACKUP_DIR")
    if not backup_dir:
        return None, "BACKUP_DIR no está configurado en el servidor"

    if not os.path.exists(backup_dir):
        return None, "El directorio de respaldos no es accesible"

    if not os.path.isdir(backup_dir):
        return None, "El directorio de respaldos no es accesible"

    if not os.access(backup_dir, os.R_OK | os.W_OK):
        return None, "El directorio de respaldos no es accesible"

    return backup_dir, None


def _parse_database_url():
    db_url = current_app.config.get("SQLALCHEMY_DATABASE_URI")
    if not db_url:
        return None

    url = make_url(db_url)
    return {
        "host": url.host or "localhost",
        "port": str(url.port or 5432),
        "username": url.username or "",
        "password": url.password or "",
        "database": url.database or "",
    }


def _generate_filename(tz=None):
    if tz is None:
        tz = current_app.config["HARVEST_TIMEZONE"]
    now = datetime.now(tz)
    return f"{_BACKUP_PREFIX}{now.strftime('%Y-%m-%d_%H%M%S_%f')}{_BACKUP_SUFFIX}"


def _format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def _file_info(filepath, tz=None):
    if tz is None:
        tz = current_app.config["HARVEST_TIMEZONE"]
    stat = os.stat(filepath)
    size_bytes = stat.st_size
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=tz)
    return {
        "filename": os.path.basename(filepath),
        "size_bytes": size_bytes,
        "size_human": _format_size(size_bytes),
        "created_at": mtime.isoformat(),
    }


def list_backups():
    backup_dir, error = _validate_backup_dir()
    if error:
        return None, error

    try:
        pattern = os.path.join(backup_dir, _BACKUP_PATTERN)
        files = glob.glob(pattern)
    except OSError:
        return None, "El directorio de respaldos no es accesible"

    backups = []
    for filepath in sorted(files, reverse=True):
        basename = os.path.basename(filepath)
        if not _valid_backup_filename(basename):
            continue
        try:
            info = _file_info(filepath)
            backups.append(info)
        except OSError:
            continue

    latest = backups[0] if backups else None

    return {
        "backup_dir_configured": True,
        "backups": backups,
        "latest": latest,
    }, None


def create_backup():
    lock = _get_lock()
    acquired = lock.acquire(blocking=False)

    if not acquired:
        return None, "Ya hay un respaldo en proceso"

    temp_path = None
    final_path = None

    try:
        backup_dir, error = _validate_backup_dir()
        if error:
            return None, error

        db_config = _parse_database_url()
        if not db_config:
            return None, "Error de configuración de base de datos"

        filename = _generate_filename()
        final_path = os.path.join(backup_dir, filename)
        temp_name = f".tmp_{uuid4().hex}"
        temp_path = os.path.join(backup_dir, temp_name)

        command = [
            current_app.config["PG_DUMP_PATH"],
            "-h", db_config["host"],
            "-p", db_config["port"],
            "-U", db_config["username"],
            "-d", db_config["database"],
            "-Fc",
            "-f", temp_path,
        ]

        env = os.environ.copy()
        env["PGPASSWORD"] = db_config["password"]

        try:
            result = subprocess.run(
                command,
                env=env,
                capture_output=True,
                text=True,
                timeout=_PG_DUMP_TIMEOUT,
            )
        except FileNotFoundError:
            return None, "pg_dump no está disponible en el sistema"
        except subprocess.TimeoutExpired:
            return None, "Error al crear el respaldo"
        finally:
            del env

        if result.returncode != 0:
            return None, "Error al crear el respaldo"

        if not os.path.isfile(temp_path) or os.path.getsize(temp_path) == 0:
            return None, "Error al crear el respaldo"

        try:
            os.replace(temp_path, final_path)
        except OSError:
            return None, "Error al crear el respaldo"

        if not os.path.isfile(final_path) or os.path.getsize(final_path) == 0:
            return None, "Error al crear el respaldo"

        info = _file_info(final_path)
        return info, None

    except Exception:
        return None, "Error al crear el respaldo"

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

        lock.release()
