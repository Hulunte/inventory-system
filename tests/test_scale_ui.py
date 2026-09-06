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
