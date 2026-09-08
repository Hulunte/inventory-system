import smtplib
from unittest.mock import patch

import pytest

from app.services.email_service import SMTPConfigError, _sanitize_filename


ENDPOINT = "/api/admin/worker-slots/export/email"
FAKE_XLSX = b"identical-worker-credentials-xlsx"
SAFE_FILENAME = "credenciales_trabajadores.xlsx"


def _csrf(client):
    return client.get("/api/admin/session").get_json()["csrf_token"]


def _post(client, email="recipient@example.com", csrf=True):
    headers = {"X-CSRF-Token": _csrf(client)} if csrf else {}
    return client.post(ENDPOINT, json={"email": email}, headers=headers)


def test_authenticated_endpoint_sends_credentials_export(admin_client):
    with patch("app.routes.admin.generate_credentials_export") as generate, patch(
        "app.routes.admin.send_export_email"
    ) as send:
        generate.return_value = (FAKE_XLSX, SAFE_FILENAME)
        response = _post(admin_client)

    assert response.status_code == 200
    assert response.get_json()["message"] == "Correo enviado exitosamente."
    send.assert_called_once()
    assert send.call_args.args[:3] == (
        "recipient@example.com",
        SAFE_FILENAME,
        FAKE_XLSX,
    )


def test_endpoint_rejects_request_without_session(client):
    response = client.post(ENDPOINT, json={"email": "recipient@example.com"})
    assert response.status_code == 401


def test_endpoint_rejects_request_without_csrf(admin_client):
    assert _post(admin_client, csrf=False).status_code == 403


@pytest.mark.parametrize(
    "email",
    ["", "invalid", "a" * 250 + "@x.com", "a@example.com\r\nBcc:x@y.com", "a@example.com;evil@example.com"],
)
def test_endpoint_rejects_invalid_or_dangerous_email(admin_client, email):
    response = _post(admin_client, email=email)
    assert response.status_code == 400
    assert response.get_json()["error"] == "Correo inválido."


def test_endpoint_reports_missing_smtp_variable(admin_client):
    with patch("app.routes.admin.generate_credentials_export", return_value=(FAKE_XLSX, SAFE_FILENAME)), patch(
        "app.routes.admin.send_export_email",
        side_effect=SMTPConfigError("Falta la variable MAIL_SMTP_USERNAME"),
    ):
        response = _post(admin_client)
    assert response.status_code == 503
    assert response.get_json()["error"] == (
        "SMTP no configurado: Falta la variable MAIL_SMTP_USERNAME"
    )


@pytest.mark.parametrize("error", [smtplib.SMTPException("offline"), OSError("offline")])
def test_endpoint_reports_smtp_connection_error(admin_client, error):
    with patch("app.routes.admin.generate_credentials_export", return_value=(FAKE_XLSX, SAFE_FILENAME)), patch(
        "app.routes.admin.send_export_email", side_effect=error
    ):
        response = _post(admin_client)
    assert response.status_code == 502
    assert response.get_json()["error"] == "Error de conexión SMTP."


def test_email_attachment_matches_normal_download(admin_client):
    with patch(
        "app.routes.admin.generate_credentials_export",
        return_value=(FAKE_XLSX, SAFE_FILENAME),
    ), patch("app.routes.admin.send_export_email") as send:
        download = admin_client.get("/api/admin/worker-slots/export")
        email = _post(admin_client)

    assert download.status_code == 200
    assert email.status_code == 200
    assert send.call_args.args[2] == download.data
    assert send.call_args.args[1] == SAFE_FILENAME


def test_worker_export_filename_is_sanitized():
    assert _sanitize_filename("../unsafe\r\nname.xlsx") == "unsafename.xlsx"


def test_admin_ui_contains_email_controls_and_spanish_messages(admin_client):
    page = admin_client.get("/admin").get_data(as_text=True)
    javascript = admin_client.get("/static/js/admin.js").get_data(as_text=True)

    assert 'id="export-slots-btn"' in page
    assert 'id="slots-email-input"' in page
    assert 'id="email-slots-btn"' in page
    assert "Enviar por correo" in page
    assert "Correo enviado exitosamente." in javascript
    assert "Correo inválido." in javascript
    assert "Error de conexión SMTP." in javascript
    assert "inventory.exportRecipientEmail" in javascript


def test_reports_and_worker_slots_share_only_browser_recipient_key(client):
    reports_js = client.get("/static/js/reports.js").get_data(as_text=True)
    admin_js = client.get("/static/js/admin.js").get_data(as_text=True)
    assert 'localStorage.setItem(EXPORT_EMAIL_STORAGE_KEY, email)' in reports_js
    assert 'localStorage.setItem(EXPORT_EMAIL_STORAGE_KEY, email)' in admin_js
    assert '"inventory.exportRecipientEmail"' in reports_js
    assert '"inventory.exportRecipientEmail"' in admin_js
