"""Tests for scale UI elements in reception page and scale.js."""
import pytest


class TestReceptionPageScaleSection:
    def test_scale_section_exists(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-section"' in html

    def test_scale_port_select(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-port-select"' in html

    def test_scale_connect_button(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-connect-btn"' in html
        assert "Conectar" in html

    def test_scale_disconnect_button(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-disconnect-btn"' in html
        assert "Desconectar" in html

    def test_scale_refresh_ports_button(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-refresh-ports"' in html
        assert "Actualizar" in html

    def test_scale_weight_value(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-weight-value"' in html

    def test_scale_stability_indicator(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-stability-indicator"' in html

    def test_scale_reading_error(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-reading-error"' in html

    def test_scale_use_weight_button(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-use-weight-btn"' in html
        assert "Usar peso" in html

    def test_scale_connection_status(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-connection-status"' in html


class TestScaleJs:
    def test_js_file_loads(self, client):
        resp = client.get("/static/js/scale.js")
        assert resp.status_code == 200

    def test_js_uses_fetch(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "fetch(" in js

    def test_js_uses_csrf_token(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "X-CSRF-Token" in js
        assert "csrf-token" in js

    def test_js_uses_textcontent(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "textContent" in js

    def test_js_no_webusb(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "webusb" not in js.lower()
        assert "WebUSB" not in js

    def test_js_no_web_serial(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "Web Serial" not in js
        assert "navigator.serial" not in js

    def test_js_no_window_print(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "window.print()" not in js

    def test_js_no_subprocess(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "subprocess" not in js
        assert "powershell" not in js.lower()
        assert "exec(" not in js

    def test_js_references_scale_api(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "/api/scale/ports" in js
        assert "/api/scale/status" in js
        assert "/api/scale/connect" in js
        assert "/api/scale/disconnect" in js

    def test_js_handles_visibility(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "visibilitychange" in js

    def test_js_has_polling(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "setInterval" in js
        assert "clearInterval" in js

    def test_js_weight_input_target(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "weight_kg" in js

    def test_js_no_numeric_float_conversion(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "parseFloat" not in js


class TestReceptionPageHasScaleScript:
    def test_scale_script_included(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert "scale.js" in html

    def test_reception_script_still_included(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert "reception.js" in html


class TestScaleJsMessages:
    def test_js_has_message_map(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "MESSAGES" in js

    def test_pyserial_unavailable_message(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "pyserial_unavailable" in js
        assert "reinstalar" in js.lower()

    def test_no_serial_ports_message(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "no_serial_ports" in js
        assert "Conecte la bascula" in js or "conecte" in js.lower()

    def test_scale_not_connected_message(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "scale_not_connected" in js
        assert "no se ha conectado" in js.lower()

    def test_port_in_use_message(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "port_in_use" in js
        assert "otra aplicacion" in js.lower() or "utilizada" in js.lower()

    def test_connected_message(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "connected" in js
        assert "conectada" in js.lower()

    def test_serial_read_error_message(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "serial_read_error" in js
        assert "no se reconoce" in js.lower() or "formato" in js.lower()

    def test_invalid_configuration_message(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "invalid_configuration" in js

    def test_messageForCode_function(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "messageForCode" in js

    def test_load_ports_uses_code(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "data.code" in js or "code" in js

    def test_updateUiFromStatus_uses_code(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "updateUiFromStatus" in js
        assert "status.code" in js or "code" in js

    def test_no_pyserial_unavailable_shown_as_default(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert '"pyserial no disponible"' not in js
        assert '"PySerial no disponible"' not in js
