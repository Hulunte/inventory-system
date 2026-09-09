"""Create a verified PostgreSQL custom-format backup without logging secrets."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


def _duplicate_critical_keys(env_file: Path) -> set[str]:
    critical = {"DATABASE_URL", "BACKUP_DIR", "PG_DUMP_PATH"}
    seen: set[str] = set()
    duplicates: set[str] = set()
    for raw_line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key in critical and key in seen:
            duplicates.add(key)
        seen.add(key)
    return duplicates


def _find_pg_dump(configured_path: str | None) -> Path | None:
    candidates: list[Path] = []
    if configured_path:
        configured = Path(configured_path.strip().strip('"'))
        candidates.append(configured / "pg_dump.exe" if configured.is_dir() else configured)
    on_path = shutil.which("pg_dump.exe") or shutil.which("pg_dump")
    if on_path:
        candidates.append(Path(on_path))
    for root in (Path(r"C:\Program Files\PostgreSQL"), Path(r"D:\Program Files\PostgreSQL")):
        if root.is_dir():
            candidates.extend(sorted(root.glob("*/bin/pg_dump.exe"), reverse=True))
            candidates.append(root / "bin" / "pg_dump.exe")
    return next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)


def create_backup(env_file: Path) -> int:
    if not env_file.is_file():
        print(f"ERROR: No se encontro el archivo .env en {env_file}.", file=sys.stderr)
        return 2
    duplicates = _duplicate_critical_keys(env_file)
    if duplicates:
        print(
            "ERROR: Configuracion duplicada en .env: " + ", ".join(sorted(duplicates)) + ".",
            file=sys.stderr,
        )
        return 3
    load_dotenv(env_file, override=True)
    database_url = os.environ.get("DATABASE_URL", "").strip()
    backup_dir_value = os.environ.get("BACKUP_DIR", "").strip().strip('"')
    if not database_url:
        print("ERROR: DATABASE_URL no esta configurada en .env.", file=sys.stderr)
        return 4
    if not backup_dir_value:
        print("ERROR: BACKUP_DIR no esta configurada en .env.", file=sys.stderr)
        return 5
    try:
        url = make_url(database_url)
    except Exception as exc:
        print(f"ERROR: DATABASE_URL no es valida ({type(exc).__name__}).", file=sys.stderr)
        return 6
    if not url.database:
        print("ERROR: DATABASE_URL no contiene el nombre de la base.", file=sys.stderr)
        return 6

    pg_dump = _find_pg_dump(os.environ.get("PG_DUMP_PATH"))
    if pg_dump is None:
        print("ERROR: No se encontro pg_dump.exe. Configure PG_DUMP_PATH.", file=sys.stderr)
        return 7

    backup_dir = Path(backup_dir_value).expanduser()
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"ERROR: No se pudo crear BACKUP_DIR ({type(exc).__name__}: {exc}).", file=sys.stderr)
        return 8
    if not backup_dir.is_dir():
        print("ERROR: BACKUP_DIR no es un directorio.", file=sys.stderr)
        return 8

    output = backup_dir / f"inventory_backup_{datetime.now():%Y%m%d_%H%M%S_%f}.dump"
    command = [
        str(pg_dump), "--format=custom", "--no-owner", "--no-privileges",
        "--host", url.host or "localhost", "--port", str(url.port or 5432),
        "--username", url.username or "postgres", "--dbname", url.database,
        "--file", str(output),
    ]
    child_env = os.environ.copy()
    child_env["PGPASSWORD"] = url.password or ""
    print(f"pg_dump: {pg_dump}")
    print(f"Destino: {output}")
    print(f"Base: {url.host or 'localhost'}:{url.port or 5432}/{url.database}")
    try:
        result = subprocess.run(command, env=child_env, capture_output=True, text=True)
    except OSError as exc:
        print(f"ERROR: No se pudo ejecutar pg_dump ({type(exc).__name__}: {exc}).", file=sys.stderr)
        return 9
    if result.returncode != 0:
        output.unlink(missing_ok=True)
        detail = (result.stderr or result.stdout or "pg_dump no proporciono detalles").strip()
        print(f"ERROR PostgreSQL (pg_dump codigo {result.returncode}): {detail}", file=sys.stderr)
        return result.returncode or 10
    try:
        size = output.stat().st_size
    except OSError as exc:
        print(f"ERROR: pg_dump termino sin un archivo verificable ({exc}).", file=sys.stderr)
        return 11
    if size <= 0:
        output.unlink(missing_ok=True)
        print("ERROR: pg_dump genero un archivo vacio.", file=sys.stderr)
        return 12
    print(f"Respaldo creado: {output}")
    print(f"Tamano: {size} bytes")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True, type=Path)
    return create_backup(parser.parse_args().env_file.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
