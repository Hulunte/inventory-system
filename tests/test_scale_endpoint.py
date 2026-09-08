"""Tests for scale API endpoints."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.scale_service import reset_scale_service, STATUS_PYSERIAL_UNAVAILABLE


@pytest.fixture(autouse=True)
def cleanup():
    yield
    reset_scale_service()


def _get_csrf(admin_client):
    return admin_client.get("/api/admin/session").get_json()["csrf_token"]


class TestScalePortsEndpoint:
    @patch("app.routes.scale.list_ports", return_value=[])
    @patch("app.routes.scale.is_available", return_value=True)
    def test_no_auth_empty_ports_returns_200(self, _available, ports, client):
        resp = client.get("/api/scale/ports")
        assert resp.status_code == 200
        assert resp.get_json()["ports"] == []
        assert resp.get_json()["message"] == "No hay puertos disponibles"
        ports.assert_called_once_with(raise_errors=True)

    @patch("app.routes.scale.list_ports", return_value=[])
    @patch("app.routes.scale.is_available", return_value=True)
    def test_admin_empty_ports_returns_200(self, _available, _ports, admin_client):
        resp = admin_client.get("/api/scale/ports")
        assert resp.status_code == 200
        assert resp.get_json()["code"] == "no_serial_ports"

    @patch("app.routes.scale.is_available", return_value=False)
    def test_pyserial_unavailable_returns_503(self, _available, client):
        resp = client.get("/api/scale/ports")
        assert resp.status_code == 503
        assert resp.get_json()["code"] == "pyserial_unavailable"
        assert resp.get_json()["message"] == "PySerial no disponible"

    @patch("app.routes.scale.list_ports", side_effect=RuntimeError("enumeration failed"))
    @patch("app.routes.scale.is_available", return_value=True)
    def test_unexpected_enumeration_error_returns_500(self, _available, _ports, client):
        resp = client.get("/api/scale/ports")
        assert resp.status_code == 500
        assert resp.get_json()["code"] == "serial_port_enumeration_error"

    def test_returns_ports_structure(self, admin_client):
        resp = admin_client.get("/api/scale/ports")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "ports" in data
        assert "available" in data
        assert "code" in data
        assert "message" in data
        assert isinstance(data["ports"], list)
        assert isinstance(data["available"], bool)
        assert isinstance(data["code"], str)
        assert isinstance(data["message"], str)

    def test_empty_ports_ui_does_not_claim_session_expired(self, client):
        javascript = client.get("/static/js/scale.js").get_data(as_text=True)
        assert 'no_serial_ports: "No hay puertos disponibles"' in javascript
        assert "Sesion expirada" not in javascript
        assert "Sesión expirada" not in javascript

    def test_anonymous_initialization_only_fetches_public_ports(self, client):
        javascript = client.get("/static/js/scale.js").get_data(as_text=True)
        init_body = javascript.split("async function init()", 1)[1].split(
            "init();", 1
        )[0]
        assert 'await loadPorts()' in init_body
        assert 'apiCall("GET", "/api/scale/status")' not in init_body
        assert "initCsrfToken" not in javascript


class TestScaleStatusEndpoint:
    def test_no_auth_returns_401(self, client):
        resp = client.get("/api/scale/status")
        assert resp.status_code == 401

    def test_returns_status_structure(self, admin_client):
        resp = admin_client.get("/api/scale/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "pyserial_available" in data
        assert "ports_available" in data
        assert "connected" in data
        assert "code" in data
        assert "message" in data
        assert "port" in data
        assert "connected_at" in data
        assert "last_reading" in data
        assert "diagnostic_mode" in data
        assert "error" in data
        assert "reconnect_attempts" in data

    def test_status_has_valid_code(self, admin_client):
        resp = admin_client.get("/api/scale/status")
        data = resp.get_json()
        valid_codes = {
            "connected", "no_serial_ports", "scale_not_connected",
            "port_in_use", "invalid_configuration", "serial_read_error",
            "pyserial_unavailable", "unsupported_platform",
        }
        assert data["code"] in valid_codes

    def test_status_message_matches_code(self, admin_client):
        resp = admin_client.get("/api/scale/status")
        data = resp.get_json()
        code = data["code"]
        msg = data["message"]
        if code == "pyserial_unavailable":
            assert "instalado" in msg.lower()
        elif code == "no_serial_ports":
            assert "puertos" in msg.lower()
        elif code == "connected":
            assert "conectada" in msg.lower()
        elif code == "scale_not_connected":
            assert "puertos" in msg.lower() or "bascula" in msg.lower()


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
        data = resp.get_json()
        assert data.get("code") == "pyserial_unavailable"


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
