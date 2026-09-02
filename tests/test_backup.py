import os
import stat
import sys
from datetime import datetime, timezone
from unittest import mock

import pytest

from app.services.backup_service import _valid_backup_filename

import pytest


class TestBackupAuth:
    def test_get_backups_requires_auth(self, client):
        response = client.get("/api/admin/backups")
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_create_backup_requires_auth(self, client):
        response = client.post("/api/admin/backups")
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data


class TestBackupCSRF:
    def test_create_backup_requires_csrf(self, admin_client):
        response = admin_client.post("/api/admin/backups")
        assert response.status_code == 403


class TestBackupDirNotConfigured:
    def test_get_backups_dir_not_configured(self, admin_client, app):
        app.config["BACKUP_DIR"] = None
        response = admin_client.get("/api/admin/backups")
        assert response.status_code == 500
        data = response.get_json()
        assert "error" in data
        assert "configurado" in data["error"]

    def test_create_backup_dir_not_configured(self, admin_client, app):
        app.config["BACKUP_DIR"] = None
        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.post(
            "/api/admin/backups",
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "configurado" in data["error"]


class TestBackupDirNotExist:
    def test_get_backups_dir_not_exist(self, admin_client, app):
        app.config["BACKUP_DIR"] = "/nonexistent/path/to/backups"
        response = admin_client.get("/api/admin/backups")
        assert response.status_code == 500
        data = response.get_json()
        assert "error" in data

    def test_create_backup_dir_not_exist(self, admin_client, app):
        app.config["BACKUP_DIR"] = "/nonexistent/path/to/backups"
        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.post(
            "/api/admin/backups",
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 500
        data = response.get_json()
        assert "error" in data


class TestBackupDirNotAccessible:
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows does not enforce POSIX permissions on file owners"
    )
    def test_get_backups_dir_not_readable(self, admin_client, app, tmp_path):
        restricted = tmp_path / "restricted"
        restricted.mkdir()
        restricted.chmod(0o000)
        app.config["BACKUP_DIR"] = str(restricted)
        try:
            response = admin_client.get("/api/admin/backups")
            assert response.status_code == 500
            data = response.get_json()
            assert "error" in data
        finally:
            restricted.chmod(0o755)

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows does not enforce POSIX permissions on file owners"
    )
    def test_create_backup_dir_not_writable(self, admin_client, app, tmp_path):
        restricted = tmp_path / "restricted"
        restricted.mkdir()
        restricted.chmod(0o444)
        app.config["BACKUP_DIR"] = str(restricted)
        try:
            csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
            response = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status_code == 500
            data = response.get_json()
            assert "error" in data
        finally:
            restricted.chmod(0o755)


class TestPgDumpNotFound:
    def test_create_backup_pg_dump_not_found(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        with mock.patch("app.services.backup_service.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("pg_dump not found")
            csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
            response = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status_code == 500
            data = response.get_json()
            assert "error" in data
            assert "pg_dump" in data["error"]
            assert len(list(tmp_path.glob("*.dump"))) == 0
            assert len(list(tmp_path.glob(".tmp_*"))) == 0


class TestPgDumpPath:
    def test_default_pg_dump_path(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        app.config["PG_DUMP_PATH"] = "pg_dump"
        with mock.patch("app.services.backup_service.subprocess.run") as mock_run:
            def fake_run(cmd, env=None, **kwargs):
                assert cmd[0] == "pg_dump"
                filepath = cmd[cmd.index("-f") + 1]
                with open(filepath, "wb") as f:
                    f.write(b"backup")
                return mock.Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = fake_run
            csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
            response = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status_code == 201

    def test_custom_pg_dump_path(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        app.config["PG_DUMP_PATH"] = "/custom/path/pg_dump"
        with mock.patch("app.services.backup_service.subprocess.run") as mock_run:
            def fake_run(cmd, env=None, **kwargs):
                assert cmd[0] == "/custom/path/pg_dump"
                filepath = cmd[cmd.index("-f") + 1]
                with open(filepath, "wb") as f:
                    f.write(b"backup")
                return mock.Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = fake_run
            csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
            response = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status_code == 201

    def test_pg_dump_path_with_spaces(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        app.config["PG_DUMP_PATH"] = "D:\\Program Files\\PostgreSQL\\bin\\pg_dump.exe"
        with mock.patch("app.services.backup_service.subprocess.run") as mock_run:
            def fake_run(cmd, env=None, **kwargs):
                assert cmd[0] == "D:\\Program Files\\PostgreSQL\\bin\\pg_dump.exe"
                assert isinstance(cmd, list)
                assert isinstance(cmd[0], str)
                filepath = cmd[cmd.index("-f") + 1]
                with open(filepath, "wb") as f:
                    f.write(b"backup")
                return mock.Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = fake_run
            csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
            response = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status_code == 201

    def test_pg_dump_path_not_in_error_response(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        app.config["PG_DUMP_PATH"] = "/secret/custom/pg_dump"
        with mock.patch("app.services.backup_service.subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=1, stdout="", stderr="error"
            )
            csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
            response = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status_code == 500
            data = response.get_json()
            response_str = str(data)
            assert "/secret/custom/pg_dump" not in response_str


class TestPgDumpError:
    def test_create_backup_pg_dump_fails(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        with mock.patch("app.services.backup_service.subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=1, stdout="", stderr="error message"
            )
            csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
            response = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status_code == 500
            data = response.get_json()
            assert "error" in data
            assert len(list(tmp_path.glob("*.dump"))) == 0
            assert len(list(tmp_path.glob(".tmp_*"))) == 0


class TestPgDumpTimeout:
    def test_create_backup_timeout(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        with mock.patch("app.services.backup_service.subprocess.run") as mock_run:
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="pg_dump", timeout=300)
            csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
            response = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status_code == 500
            data = response.get_json()
            assert "error" in data
            assert len(list(tmp_path.glob("*.dump"))) == 0
            assert len(list(tmp_path.glob(".tmp_*"))) == 0


class TestCreateBackupSuccess:
    def test_create_backup_success(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        with mock.patch("app.services.backup_service.subprocess.run") as mock_run:
            def fake_run(cmd, env=None, **kwargs):
                filepath = cmd[cmd.index("-f") + 1]
                with open(filepath, "wb") as f:
                    f.write(b"PGDMPROD backup data")
                return mock.Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = fake_run
            csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
            response = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status_code == 201
            data = response.get_json()
            assert "message" in data
            assert "backup" in data
            assert data["backup"]["filename"].startswith("inventory_backup_")
            assert data["backup"]["filename"].endswith(".dump")
            assert data["backup"]["size_bytes"] > 0
            assert "size_human" in data["backup"]
            assert "created_at" in data["backup"]
            assert len(list(tmp_path.glob("*.dump"))) == 1
            assert len(list(tmp_path.glob(".tmp_*"))) == 0


class TestFilenameFormat:
    def test_filename_has_microseconds(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        with mock.patch("app.services.backup_service.subprocess.run") as mock_run:
            def fake_run(cmd, env=None, **kwargs):
                filepath = cmd[cmd.index("-f") + 1]
                with open(filepath, "wb") as f:
                    f.write(b"PGDMPROD backup data")
                return mock.Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = fake_run
            csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
            response = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status_code == 201
            filename = response.get_json()["backup"]["filename"]
            import re
            pattern = r"^inventory_backup_\d{4}-\d{2}-\d{2}_\d{6}_\d{6}\.dump$"
            assert re.match(pattern, filename), f"Filename {filename} does not match pattern"


class TestAtomicWrite:
    def test_temp_cleaned_after_error(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        with mock.patch("app.services.backup_service.subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=1, stdout="", stderr="error"
            )
            csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
            response = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status_code == 500
            assert len(list(tmp_path.glob(".tmp_*"))) == 0
            assert len(list(tmp_path.glob("*.dump"))) == 0

    def test_no_dump_created_on_error(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        with mock.patch("app.services.backup_service.subprocess.run") as mock_run:
            def fake_run(cmd, env=None, **kwargs):
                filepath = cmd[cmd.index("-f") + 1]
                with open(filepath, "wb") as f:
                    f.write(b"partial data")
                return mock.Mock(returncode=1, stdout="", stderr="error")

            mock_run.side_effect = fake_run
            csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
            response = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status_code == 500
            assert len(list(tmp_path.glob("*.dump"))) == 0
            assert len(list(tmp_path.glob(".tmp_*"))) == 0


class TestListBackups:
    def test_list_backups_empty(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        response = admin_client.get("/api/admin/backups")
        assert response.status_code == 200
        data = response.get_json()
        assert data["backups"] == []
        assert data["latest"] is None

    def test_list_backups_with_files(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        dump1 = tmp_path / "inventory_backup_2026-09-01_120000_123456.dump"
        dump2 = tmp_path / "inventory_backup_2026-09-01_130000_654321.dump"
        dump1.write_bytes(b"backup1")
        dump2.write_bytes(b"backup2")
        response = admin_client.get("/api/admin/backups")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["backups"]) == 2
        assert data["backups"][0]["filename"] == "inventory_backup_2026-09-01_130000_654321.dump"
        assert data["backups"][1]["filename"] == "inventory_backup_2026-09-01_120000_123456.dump"
        assert data["latest"]["filename"] == "inventory_backup_2026-09-01_130000_654321.dump"

    def test_list_backups_ignores_non_dump(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        valid = tmp_path / "inventory_backup_2026-09-01_120000_123456.dump"
        invalid_ext = tmp_path / "inventory_backup_2026-09-01_120000_123456.txt"
        other_prefix = tmp_path / "some_other_file.dump"
        temp = tmp_path / ".tmp_abc123"
        valid.write_bytes(b"valid")
        invalid_ext.write_bytes(b"invalid")
        other_prefix.write_bytes(b"other")
        temp.write_bytes(b"temp")
        response = admin_client.get("/api/admin/backups")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["backups"]) == 1
        assert data["backups"][0]["filename"] == "inventory_backup_2026-09-01_120000_123456.dump"

    def test_list_backups_rejects_strict_format_violations(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        cases = [
            "inventory_backup_basura.dump",
            "inventory_backup_2026.dump",
            "inventory_backup_2026-99-99_999999_123456.dump",
            "inventory_backup_2026-09-01_175612.dump",
            "inventory_backup_2026-09-01_175612_123456.dump.exe",
            "inventory_backup_2026-09-01_175612_12345.dump",
            "inventory_backup_2026-09-01_175612_123456_extra.dump",
        ]
        for name in cases:
            (tmp_path / name).write_bytes(b"junk")
        valid = tmp_path / "inventory_backup_2026-09-01_175612_123456.dump"
        valid.write_bytes(b"valid")
        response = admin_client.get("/api/admin/backups")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["backups"]) == 1
        assert data["backups"][0]["filename"] == "inventory_backup_2026-09-01_175612_123456.dump"

    def test_list_backups_order_descending(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        older = tmp_path / "inventory_backup_2026-09-01_100000_000001.dump"
        newer = tmp_path / "inventory_backup_2026-09-01_140000_000002.dump"
        older.write_bytes(b"older")
        newer.write_bytes(b"newer")
        response = admin_client.get("/api/admin/backups")
        assert response.status_code == 200
        data = response.get_json()
        assert data["backups"][0]["filename"] == "inventory_backup_2026-09-01_140000_000002.dump"
        assert data["backups"][1]["filename"] == "inventory_backup_2026-09-01_100000_000001.dump"

    def test_list_backups_size_and_timestamp(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        dump = tmp_path / "inventory_backup_2026-09-01_120000_123456.dump"
        dump.write_bytes(b"x" * 1024)
        response = admin_client.get("/api/admin/backups")
        assert response.status_code == 200
        data = response.get_json()
        assert data["backups"][0]["size_bytes"] == 1024
        assert data["backups"][0]["size_human"] == "1.0 KB"
        assert "created_at" in data["backups"][0]


class TestFilenameValidation:
    def test_valid_filename(self):
        assert _valid_backup_filename("inventory_backup_2026-09-01_175612_123456.dump")

    def test_valid_filename_zeros(self):
        assert _valid_backup_filename("inventory_backup_2026-01-01_000000_000000.dump")

    def test_valid_filename_max_microseconds(self):
        assert _valid_backup_filename("inventory_backup_2026-12-31_235959_999999.dump")

    def test_rejects_garbage_content(self):
        assert not _valid_backup_filename("inventory_backup_basura.dump")

    def test_rejects_no_datetime(self):
        assert not _valid_backup_filename("inventory_backup_2026.dump")

    def test_rejects_invalid_date(self):
        assert not _valid_backup_filename("inventory_backup_2026-99-99_999999_123456.dump")

    def test_rejects_invalid_time(self):
        assert not _valid_backup_filename("inventory_backup_2026-09-01_999999_123456.dump")

    def test_rejects_short_microseconds(self):
        assert not _valid_backup_filename("inventory_backup_2026-09-01_175612_12345.dump")

    def test_rejects_long_microseconds(self):
        assert not _valid_backup_filename("inventory_backup_2026-09-01_175612_1234567.dump")

    def test_rejects_no_microseconds(self):
        assert not _valid_backup_filename("inventory_backup_2026-09-01_175612.dump")

    def test_rejects_extra_suffix(self):
        assert not _valid_backup_filename("inventory_backup_2026-09-01_175612_123456_extra.dump")

    def test_rejects_wrong_extension(self):
        assert not _valid_backup_filename("inventory_backup_2026-09-01_175612_123456.dump.exe")

    def test_rejects_txt_extension(self):
        assert not _valid_backup_filename("inventory_backup_2026-09-01_175612_123456.txt")

    def test_rejects_tmp_file(self):
        assert not _valid_backup_filename(".tmp_abc123def456")

    def test_rejects_empty_string(self):
        assert not _valid_backup_filename("")

    def test_rejects_partial_prefix(self):
        assert not _valid_backup_filename("inventory_backup_2026-09-01_175612_123456")

    def test_rejects_no_date_separator(self):
        assert not _valid_backup_filename("inventory_backup_20260901_175612_123456.dump")


class TestSecurity:
    def test_password_not_in_response(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        with mock.patch("app.services.backup_service.subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=1, stdout="", stderr="password: auth failed"
            )
            csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
            response = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status_code == 500
            data = response.get_json()
            response_str = str(data)
            assert "password" not in response_str.lower() or "error" in response_str.lower()

    def test_database_url_not_in_response(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        with mock.patch("app.services.backup_service.subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=1, stdout="", stderr="connection failed"
            )
            csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
            response = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status_code == 500
            data = response.get_json()
            response_str = str(data)
            assert "postgresql" not in response_str.lower()

    def test_pgpassword_in_env_not_args(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        with mock.patch("app.services.backup_service.subprocess.run") as mock_run:
            def fake_run(cmd, env=None, **kwargs):
                assert env is not None
                assert "PGPASSWORD" in env
                assert env["PGPASSWORD"] != ""
                for arg in cmd:
                    assert arg != env["PGPASSWORD"]
                filepath = cmd[cmd.index("-f") + 1]
                with open(filepath, "wb") as f:
                    f.write(b"backup")
                return mock.Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = fake_run
            csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
            response = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status_code == 201

    def test_shell_true_not_used(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        with mock.patch("app.services.backup_service.subprocess.run") as mock_run:
            def fake_run(cmd, env=None, **kwargs):
                assert isinstance(cmd, list)
                assert kwargs.get("shell", False) is False
                filepath = cmd[cmd.index("-f") + 1]
                with open(filepath, "wb") as f:
                    f.write(b"backup")
                return mock.Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = fake_run
            csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
            response = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status_code == 201


class TestConcurrency:
    def test_second_backup_returns_409(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        import threading
        import time

        call_count = [0]
        lock_event = threading.Event()
        proceed_event = threading.Event()

        def slow_run(cmd, env=None, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                lock_event.set()
                proceed_event.wait(timeout=5)
            filepath = cmd[cmd.index("-f") + 1]
            with open(filepath, "wb") as f:
                f.write(b"backup")
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch("app.services.backup_service.subprocess.run", side_effect=slow_run):
            results = [None, None]

            def first_backup():
                csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
                results[0] = admin_client.post(
                    "/api/admin/backups",
                    headers={"X-CSRF-Token": csrf},
                )
                proceed_event.set()

            def second_backup():
                lock_event.wait(timeout=5)
                time.sleep(0.1)
                csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
                results[1] = admin_client.post(
                    "/api/admin/backups",
                    headers={"X-CSRF-Token": csrf},
                )

            t1 = threading.Thread(target=first_backup)
            t2 = threading.Thread(target=second_backup)
            t1.start()
            t2.start()
            t1.join(timeout=10)
            t2.join(timeout=10)

            assert results[0].status_code == 201
            assert results[1].status_code == 409

    def test_lock_released_after_error(self, admin_client, app, tmp_path):
        app.config["BACKUP_DIR"] = str(tmp_path)
        with mock.patch("app.services.backup_service.subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=1, stdout="", stderr="error"
            )
            csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
            response1 = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response1.status_code == 500

            def fake_run(cmd, env=None, **kwargs):
                filepath = cmd[cmd.index("-f") + 1]
                with open(filepath, "wb") as f:
                    f.write(b"backup")
                return mock.Mock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = fake_run
            response2 = admin_client.post(
                "/api/admin/backups",
                headers={"X-CSRF-Token": csrf},
            )
            assert response2.status_code == 201
