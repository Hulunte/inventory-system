import smtplib
from unittest.mock import patch

import pytest

from app.services.email_service import SMTPConfigError


def _get_csrf(admin_client):
    return admin_client.get("/api/admin/session").get_json()["csrf_token"]


class TestEmailEndpointSuccess:
    def test_success(self, admin_client):
        csrf = _get_csrf(admin_client)
        with patch("app.routes.reports.send_export_email") as mock_send:
            resp = admin_client.post(
                "/api/reports/harvest/export/email",
                json={
                    "email": "test@example.com",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                },
                headers={"X-CSRF-Token": csrf},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert "test@example.com" in data["message"]
            mock_send.assert_called_once()

    def test_with_query_filter(self, admin_client):
        csrf = _get_csrf(admin_client)
        with patch("app.routes.reports.send_export_email") as mock_send:
            resp = admin_client.post(
                "/api/reports/harvest/export/email",
                json={
                    "email": "test@example.com",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                    "q": "WorkerName",
                },
                headers={"X-CSRF-Token": csrf},
            )
            assert resp.status_code == 200
            mock_send.assert_called_once()

    def test_response_in_spanish(self, admin_client):
        csrf = _get_csrf(admin_client)
        with patch("app.routes.reports.send_export_email"):
            resp = admin_client.post(
                "/api/reports/harvest/export/email",
                json={
                    "email": "test@example.com",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                },
                headers={"X-CSRF-Token": csrf},
            )
            data = resp.get_json()
            assert "Correo" in data["message"]
            assert "test@example.com" in data["message"]


class TestEmailEndpointAuth:
    def test_no_auth_returns_401(self, client):
        resp = client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "test@example.com",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
        )
        assert resp.status_code == 401

    def test_csrf_invalid_returns_403(self, admin_client):
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "test@example.com",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
            headers={"X-CSRF-Token": "invalid-token"},
        )
        assert resp.status_code == 403
        assert "CSRF" in resp.get_json()["error"]

    def test_no_csrf_header_returns_403(self, admin_client):
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "test@example.com",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
        )
        assert resp.status_code == 403


class TestEmailEndpointCsrfSelfContained:
    def test_admin_module_not_aware_of_reports(self):
        import app.routes.admin as admin_mod
        import inspect
        source = inspect.getsource(admin_mod.require_csrf)
        assert "/api/reports/" not in source

    def test_csrf_validation_works_for_reports(self, admin_client):
        csrf = _get_csrf(admin_client)
        with patch("app.routes.reports.send_export_email"):
            resp = admin_client.post(
                "/api/reports/harvest/export/email",
                json={
                    "email": "test@example.com",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                },
                headers={"X-CSRF-Token": csrf},
            )
            assert resp.status_code == 200


class TestEmailEndpointValidation:
    def test_invalid_json(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            data="not json",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_json_not_object(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json="string",
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_unknown_field(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "test@example.com",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "bcc": "evil@example.com",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400
        assert "Unknown fields" in resp.get_json()["error"]

    def test_email_missing(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400
        assert "email" in resp.get_json()["error"].lower()

    def test_email_empty(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_email_whitespace_only(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "   ",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_email_invalid_format(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "not-an-email",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400
        assert "Invalid email" in resp.get_json()["error"]

    def test_email_no_at(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "userexample.com",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_email_no_domain(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "user@",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_email_non_string_rejected(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": 123,
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_email_internal_whitespace_rejected(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "user @example.com",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_email_comma_rejected(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "a@example.com,b@example.com",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_email_semicolon_rejected(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "a@example.com;b@example.com",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_email_display_name_rejected(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "User Name <user@example.com>",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_email_angle_brackets_rejected(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "<user@example.com>",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize("bad_email", [
        "user@\nexample.com",
        "user@\r\nexample.com",
        "user\r@example.com",
        "user\n@example.com",
    ])
    def test_crlf_injection_rejected(self, admin_client, bad_email):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": bad_email,
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_start_date_missing(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "test@example.com",
                "end_date": "2026-01-31",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_end_date_missing(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "test@example.com",
                "start_date": "2026-01-01",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_invalid_start_date(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "test@example.com",
                "start_date": "not-a-date",
                "end_date": "2026-01-31",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_invalid_end_date(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "test@example.com",
                "start_date": "2026-01-01",
                "end_date": "not-a-date",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_start_after_end(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/reports/harvest/export/email",
            json={
                "email": "test@example.com",
                "start_date": "2026-12-31",
                "end_date": "2026-01-01",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400


class TestEmailEndpointErrors:
    def test_smtp_missing_config_returns_503(self, admin_client):
        csrf = _get_csrf(admin_client)
        with patch("app.routes.reports.send_export_email") as mock_send:
            mock_send.side_effect = SMTPConfigError("SMTP configuration is incomplete")
            resp = admin_client.post(
                "/api/reports/harvest/export/email",
                json={
                    "email": "test@example.com",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                },
                headers={"X-CSRF-Token": csrf},
            )
            assert resp.status_code == 503
            assert "configured" in resp.get_json()["error"].lower()

    def test_smtp_failure_returns_502(self, admin_client):
        csrf = _get_csrf(admin_client)
        with patch("app.routes.reports.send_export_email") as mock_send:
            mock_send.side_effect = smtplib.SMTPException("Connection refused")
            resp = admin_client.post(
                "/api/reports/harvest/export/email",
                json={
                    "email": "test@example.com",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                },
                headers={"X-CSRF-Token": csrf},
            )
            assert resp.status_code == 502
            assert "Failed to send email" in resp.get_json()["error"]

    def test_os_error_returns_502(self, admin_client):
        csrf = _get_csrf(admin_client)
        with patch("app.routes.reports.send_export_email") as mock_send:
            mock_send.side_effect = OSError("Network unreachable")
            resp = admin_client.post(
                "/api/reports/harvest/export/email",
                json={
                    "email": "test@example.com",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                },
                headers={"X-CSRF-Token": csrf},
            )
            assert resp.status_code == 502
            assert "Failed to send email" in resp.get_json()["error"]

    def test_no_internal_details_in_error(self, admin_client):
        csrf = _get_csrf(admin_client)
        with patch("app.routes.reports.send_export_email") as mock_send:
            mock_send.side_effect = smtplib.SMTPException("Internal SMTP error 421")
            resp = admin_client.post(
                "/api/reports/harvest/export/email",
                json={
                    "email": "test@example.com",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                },
                headers={"X-CSRF-Token": csrf},
            )
            error_msg = resp.get_json()["error"]
            assert "421" not in error_msg
            assert "Internal SMTP" not in error_msg

    def test_empty_xlsx_returns_500(self, admin_client):
        csrf = _get_csrf(admin_client)
        with patch("app.routes.reports.generate_harvest_export") as mock_gen:
            mock_gen.return_value = (b"", "empty.xlsx")
            resp = admin_client.post(
                "/api/reports/harvest/export/email",
                json={
                    "email": "test@example.com",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                },
                headers={"X-CSRF-Token": csrf},
            )
            assert resp.status_code == 500
            assert "empty" in resp.get_json()["error"].lower()


class TestEmailEndpointReusesExporter:
    def test_generates_excel_with_same_filters(self, admin_client):
        csrf = _get_csrf(admin_client)
        with patch("app.routes.reports.send_export_email") as mock_send, \
             patch("app.routes.reports.generate_harvest_export") as mock_gen:
            mock_gen.return_value = (b"fake-xlsx", "test.xlsx")

            resp = admin_client.post(
                "/api/reports/harvest/export/email",
                json={
                    "email": "test@example.com",
                    "start_date": "2026-03-10",
                    "end_date": "2026-03-15",
                    "q": "WorkerName",
                },
                headers={"X-CSRF-Token": csrf},
            )

            assert resp.status_code == 200
            mock_gen.assert_called_once()
            call_args = mock_gen.call_args
            assert str(call_args[0][0]) == "2026-03-10"
            assert str(call_args[0][1]) == "2026-03-15"
            assert call_args[0][2] == "WorkerName"

            sent_msg = mock_send.call_args[0][2]
            assert sent_msg == b"fake-xlsx"

    def test_download_and_email_use_same_generator(self, admin_client):
        csrf = _get_csrf(admin_client)
        with patch("app.routes.reports.send_export_email") as mock_send, \
             patch("app.routes.reports.generate_harvest_export") as mock_gen:
            mock_gen.return_value = (b"fake-xlsx", "test.xlsx")

            admin_client.get(
                "/api/reports/harvest/export?start_date=2026-01-01&end_date=2026-01-31",
            )
            get_call = mock_gen.call_args

            admin_client.post(
                "/api/reports/harvest/export/email",
                json={
                    "email": "test@example.com",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                },
                headers={"X-CSRF-Token": csrf},
            )
            post_call = mock_gen.call_args

            assert get_call[0][0] == post_call[0][0]
            assert get_call[0][1] == post_call[0][1]
            assert get_call[0][2] == post_call[0][2]


class TestNoRealGmailConnection:
    def test_smtp_never_called_with_real_host(self, admin_client):
        csrf = _get_csrf(admin_client)
        with patch("app.routes.reports.send_export_email") as mock_send:
            mock_send.return_value = None

            resp = admin_client.post(
                "/api/reports/harvest/export/email",
                json={
                    "email": "test@example.com",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                },
                headers={"X-CSRF-Token": csrf},
            )

            assert resp.status_code == 200
            mock_send.assert_called_once()

            call_kwargs = mock_send.call_args
            assert call_kwargs[0][0] == "test@example.com"
