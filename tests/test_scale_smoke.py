"""Smoke tests for scale integration package.

Validates that:
1. import serial works
2. serial.tools.list_ports works
3. Absence of scale does not cause fatal errors
4. Application starts without a scale connected
5. Manual capture continues to work
6. The status code is NOT pyserial_unavailable when list_ports returns empty
"""
import pytest


class TestPySerialImport:
    def test_import_serial(self):
        import serial
        assert hasattr(serial, "__version__")

    def test_import_list_ports(self):
        import serial.tools.list_ports
        assert hasattr(serial.tools.list_ports, "comports")

    def test_list_ports_callable(self):
        import serial.tools.list_ports
        result = serial.tools.list_ports.comports()
        assert isinstance(result, list)


class TestScaleServiceWithoutScale:
    def test_app_starts(self, admin_client):
        resp = admin_client.get("/")
        assert resp.status_code == 200

    def test_scale_status_endpoint_works(self, admin_client):
        resp = admin_client.get("/api/scale/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "code" in data
        assert "message" in data
        assert "connected" in data

    def test_scale_ports_endpoint_works(self, admin_client):
        resp = admin_client.get("/api/scale/ports")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "ports" in data
        assert "available" in data
        assert "code" in data

    def test_status_not_pyserial_unavailable_when_no_ports(self, admin_client):
        resp = admin_client.get("/api/scale/status")
        data = resp.get_json()
        assert data["pyserial_available"] is True
        assert data["code"] != "pyserial_unavailable"

    def test_reception_page_loads(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert "scale-section" in html
        assert "scale.js" in html


class TestManualCaptureUnaffected:
    def test_reception_page_has_worker_input(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert "barcode" in html.lower() or "trabajador" in html.lower()

    def test_reception_page_has_weight_input(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert "weight" in html.lower()

    def test_reception_page_has_product_selector(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert "product-selector" in html or "product" in html.lower()

    def test_reception_js_loads(self, client):
        resp = client.get("/static/js/reception.js")
        assert resp.status_code == 200
