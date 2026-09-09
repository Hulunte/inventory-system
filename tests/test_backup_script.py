import importlib.util
from pathlib import Path
import subprocess


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "backup.py"
spec = importlib.util.spec_from_file_location("backup_script", SCRIPT_PATH)
backup_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup_script)


def _write_env(path, backup_dir, pg_dump):
    path.write_text(
        "DATABASE_URL=postgresql+psycopg://inventory_user:private-password@localhost:5432/inventory_db\n"
        f"BACKUP_DIR={backup_dir}\n"
        f"PG_DUMP_PATH={pg_dump}\n",
        encoding="utf-8",
    )


def test_backup_uses_paths_with_spaces_and_verifies_dump(tmp_path, monkeypatch, capsys):
    pg_dump = tmp_path / "Program Files" / "PostgreSQL" / "bin" / "pg_dump.exe"
    pg_dump.parent.mkdir(parents=True)
    pg_dump.write_bytes(b"exe")
    backup_dir = tmp_path / "Backup Folder"
    env_file = tmp_path / ".env"
    _write_env(env_file, backup_dir, pg_dump)

    def fake_run(command, **kwargs):
        output = Path(command[command.index("--file") + 1])
        output.write_bytes(b"PGDMP-valid")
        assert kwargs["env"]["PGPASSWORD"] == "private-password"
        assert "private-password" not in command
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(backup_script.subprocess, "run", fake_run)
    assert backup_script.create_backup(env_file) == 0
    output = capsys.readouterr()
    assert "private-password" not in output.out + output.err
    dumps = list(backup_dir.glob("*.dump"))
    assert len(dumps) == 1
    assert dumps[0].stat().st_size == 11


def test_backup_returns_pg_dump_exit_code_and_removes_partial_file(tmp_path, monkeypatch, capsys):
    pg_dump = tmp_path / "pg_dump.exe"
    pg_dump.write_bytes(b"exe")
    backup_dir = tmp_path / "backups"
    env_file = tmp_path / ".env"
    _write_env(env_file, backup_dir, pg_dump)

    def fake_run(command, **_kwargs):
        Path(command[command.index("--file") + 1]).write_bytes(b"partial")
        return subprocess.CompletedProcess(command, 1, "", "pg_dump: authentication failed")

    monkeypatch.setattr(backup_script.subprocess, "run", fake_run)
    assert backup_script.create_backup(env_file) == 1
    output = capsys.readouterr()
    assert "pg_dump codigo 1" in output.err
    assert "authentication failed" in output.err
    assert not list(backup_dir.glob("*.dump"))


def test_backup_rejects_duplicate_critical_configuration(tmp_path, capsys):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql://u:p@localhost/db\n"
        "BACKUP_DIR=C:\\one\nBACKUP_DIR=D:\\two\n",
        encoding="utf-8",
    )
    assert backup_script.create_backup(env_file) == 3
    assert "BACKUP_DIR" in capsys.readouterr().err


def test_batch_uses_absolute_script_paths_and_propagates_exit_code():
    batch = (Path(__file__).parents[1] / "scripts" / "backup.bat").read_text(encoding="utf-8")
    assert "%~dp0" in batch
    assert '"%PYTHON_EXE%" "%SCRIPT_DIR%backup.py"' in batch
    assert "exit /b %BACKUP_EXIT_CODE%" in batch
    assert "python -c" not in batch
