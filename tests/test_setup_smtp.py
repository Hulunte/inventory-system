import json
import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

from app.services.email_service import send_export_email


SMTP_PAYLOAD = {
    "admin_password": "valid-admin-password",
    "smtp_host": "smtp.example.test",
    "smtp_port": "587",
    "smtp_username": "sender@example.test",
    "smtp_app_password": "fake-application-password",
}

SMTP_KEYS = (
    "MAIL_SMTP_HOST",
    "MAIL_SMTP_PORT",
    "MAIL_SMTP_USERNAME",
    "MAIL_SMTP_APP_PASSWORD",
    "MAIL_FROM_ADDRESS",
    "MAIL_FROM_NAME",
    "MAIL_USE_TLS",
    "MAIL_TIMEOUT_SECONDS",
)


def _configure_smtp(client, app, tmp_path, monkeypatch):
    from app.routes import views

    monkeypatch.setattr(views, "_get_base_dir", lambda: str(tmp_path))
    (tmp_path / ".env").write_text(
        "DATABASE_URL=postgresql+psycopg://user:password@localhost/database\n"
        f"SECRET_KEY={'s' * 64}\n",
        encoding="utf-8",
    )
    response = client.post("/api/setup", json=SMTP_PAYLOAD)
    assert response.status_code == 200
    return tmp_path / ".env"


def test_setup_persists_complete_smtp_and_updates_running_app(
    client, app, tmp_path, monkeypatch
):
    env_file = _configure_smtp(client, app, tmp_path, monkeypatch)
    content = env_file.read_text(encoding="utf-8")

    expected = {
        "MAIL_SMTP_HOST": "smtp.example.test",
        "MAIL_SMTP_PORT": "587",
        "MAIL_SMTP_USERNAME": "sender@example.test",
        "MAIL_SMTP_APP_PASSWORD": "fake-application-password",
        "MAIL_FROM_ADDRESS": "sender@example.test",
        "MAIL_FROM_NAME": "Sistema de Cosecha",
        "MAIL_USE_TLS": "true",
        "MAIL_TIMEOUT_SECONDS": "30",
    }
    for key, value in expected.items():
        assert f"{key}={value}" in content
        assert os.environ[key] == value
        configured = app.config[key]
        assert str(configured).lower() == value.lower()


def test_setup_smtp_can_send_without_restart(client, app, tmp_path, monkeypatch):
    _configure_smtp(client, app, tmp_path, monkeypatch)
    smtp_server = MagicMock()

    with patch("app.services.email_service.smtplib.SMTP") as smtp_class:
        smtp_class.return_value.__enter__.return_value = smtp_server
        smtp_class.return_value.__exit__.return_value = False
        send_export_email(
            "recipient@example.test", "report.xlsx", b"fake-xlsx", app.config
        )

    smtp_class.assert_called_once_with("smtp.example.test", 587, timeout=30)
    smtp_server.login.assert_called_once_with(
        "sender@example.test", "fake-application-password"
    )
    smtp_server.send_message.assert_called_once()


def test_smtp_configuration_loads_after_process_restart(
    client, app, tmp_path, monkeypatch
):
    _configure_smtp(client, app, tmp_path, monkeypatch)
    process_env = os.environ.copy()
    for key in SMTP_KEYS:
        process_env.pop(key, None)
    process_env["PYTHONPATH"] = str(os.path.dirname(os.path.dirname(__file__)))

    script = (
        "import json; from config import Config; "
        "print(json.dumps({k: getattr(Config, k) for k in "
        + repr(SMTP_KEYS)
        + "}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=process_env,
        check=True,
        capture_output=True,
        text=True,
    )
    loaded = json.loads(result.stdout)
    assert loaded["MAIL_SMTP_HOST"] == "smtp.example.test"
    assert loaded["MAIL_SMTP_PORT"] == 587
    assert loaded["MAIL_SMTP_USERNAME"] == "sender@example.test"
    assert loaded["MAIL_FROM_ADDRESS"] == "sender@example.test"
    assert loaded["MAIL_USE_TLS"] == "true"
    assert loaded["MAIL_TIMEOUT_SECONDS"] == 30


def test_setup_rejects_partial_smtp_configuration(client, tmp_path, monkeypatch):
    from app.routes import views

    monkeypatch.setattr(views, "_get_base_dir", lambda: str(tmp_path))
    (tmp_path / ".env").write_text(
        "DATABASE_URL=postgresql+psycopg://user:password@localhost/database\n",
        encoding="utf-8",
    )
    response = client.post(
        "/api/setup",
        json={
            "admin_password": "valid-admin-password",
            "smtp_host": "smtp.example.test",
        },
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "Falta la variable MAIL_SMTP_USERNAME"
    assert "ADMIN_PASSWORD_HASH" not in (tmp_path / ".env").read_text(encoding="utf-8")
