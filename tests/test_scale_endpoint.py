"""Tests for scale API endpoints."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.scale_service import reset_scale_service


@pytest.fixture(autouse=True)
def cleanup():
    yield
    reset_scale_service()


def _get_csrf(admin_client):
    return admin_client.get("/api/admin/session").get_json()["csrf_token"]


class TestScalePortsEndpoint:
    def test_no_auth_returns_401(self, client):
        resp = client.get("/api/scale/ports")
        assert resp.status_code == 401

    def test_returns_ports_structure(self, admin_client):
        resp = admin_client.get("/api/scale/ports")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "ports" in data
        assert "available" in data
        assert isinstance(data["ports"], list)
        assert isinstance(data["available"], bool)


class TestScaleStatusEndpoint:
    def test_no_auth_returns_401(self, client):
        resp = client.get("/api/scale/status")
        assert resp.status_code == 401

    def test_returns_status_structure(self, admin_client):
        resp = admin_client.get("/api/scale/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "available" in data
        assert "connected" in data
        assert "port" in data
        assert "connected_at" in data
        assert "last_reading" in data
        assert "diagnostic_mode" in data
        assert "error" in data
        assert "reconnect_attempts" in data


class TestScaleConnectEndpoint:
    def test_no_auth_returns_401(self, client):
        resp = client.post("/api/scale/connect", json={"port": "COM7"})
        assert resp.status_code == 401

    def test_no_csrf_returns_403(self, admin_client):
        resp = admin_client.post("/api/scale/connect", json={"port": "COM7"})
        assert resp.status_code == 403

    def test_missing_port(self, admin_client):
        csrf = _get_csrf(admin_client)
        with patch("app.routes.scale.is_available", return_value=True):
            resp = admin_client.post(
                "/api/scale/connect",
                json={},
                headers={"X-CSRF-Token": csrf},
            )
        assert resp.status_code == 400
        assert "port" in resp.get_json()["error"].lower()

    def test_invalid_port_name(self, admin_client):
        csrf = _get_csrf(admin_client)
        with patch("app.routes.scale.is_available", return_value=True):
            resp = admin_client.post(
                "/api/scale/connect",
                json={"port": ""},
                headers={"X-CSRF-Token": csrf},
            )
        assert resp.status_code == 400

    def test_unknown_fields_rejected(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/scale/connect",
            json={"port": "COM7", "unknown_field": True},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400
        assert "Unknown fields" in resp.get_json()["error"]

    def test_invalid_json_body(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/scale/connect",
            data="not json",
            headers={"X-CSRF-Token": csrf, "Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_non_dict_json_rejected(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/scale/connect",
            json=[1, 2, 3],
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    @patch("app.routes.scale.is_available", return_value=False)
    def test_unavailable_returns_503(self, mock_avail, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/scale/connect",
            json={"port": "COM7"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 503


class TestScaleDisconnectEndpoint:
    def test_no_auth_returns_401(self, client):
        resp = client.post("/api/scale/disconnect")
        assert resp.status_code == 401

    def test_no_csrf_returns_403(self, admin_client):
        resp = admin_client.post("/api/scale/disconnect")
        assert resp.status_code == 403

    def test_not_connected_returns_409(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/scale/disconnect",
            json={},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 409


class TestScaleTestEndpoint:
    def test_no_auth_returns_401(self, client):
        resp = client.post("/api/scale/test")
        assert resp.status_code == 401

    def test_not_connected_returns_409(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/scale/test",
            json={},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 409


class TestScaleDiagnosticEndpoint:
    def test_no_auth_returns_401(self, client):
        resp = client.post("/api/scale/diagnostic", json={"enabled": True})
        assert resp.status_code == 401

    def test_no_csrf_returns_403(self, admin_client):
        resp = admin_client.post("/api/scale/diagnostic", json={"enabled": True})
        assert resp.status_code == 403

    def test_missing_enabled(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/scale/diagnostic",
            json={},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_enabled_not_bool(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/scale/diagnostic",
            json={"enabled": "yes"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_toggle_diagnostic(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/scale/diagnostic",
            json={"enabled": True},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["diagnostic_mode"] is True

    def test_invalid_json_body(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/scale/diagnostic",
            data="not json",
            headers={"X-CSRF-Token": csrf, "Content-Type": "application/json"},
        )
        assert resp.status_code == 400
