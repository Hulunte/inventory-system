"""Tests for scale service (mocked serial)."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.scale_config import ScaleConfig
from app.services.scale_parser import WeightReading
from app.services.scale_service import (
    ScaleConnectionError,
    ScaleService,
    ScaleUnavailableError,
    is_available,
    list_ports,
    reset_scale_service,
    get_scale_service,
    STATUS_CONNECTED,
    STATUS_NO_SERIAL_PORTS,
    STATUS_SCALE_NOT_CONNECTED,
    STATUS_PORT_IN_USE,
    STATUS_INVALID_CONFIGURATION,
    STATUS_SERIAL_READ_ERROR,
    STATUS_PYSERIAL_UNAVAILABLE,
    STATUS_UNSUPPORTED_PLATFORM,
)


@pytest.fixture(autouse=True)
def cleanup_service():
    yield
    reset_scale_service()


def _make_config(port="COM7"):
    return ScaleConfig(
        port=port,
        baudrate=9600,
        bytesize=8,
        parity="N",
        stopbits=1.0,
        timeout_seconds=0.1,
        line_encoding="ascii",
        profile="auto",
        min_weight_kg="0.001",
        max_weight_kg="999.999",
    )


def _make_mock_serial(read_value=None):
    mock = MagicMock()
    mock.is_open = True
    if read_value is None:
        mock.readline.return_value = b""
    elif isinstance(read_value, str):
        mock.readline.return_value = read_value.encode("ascii")
    else:
        mock.readline.return_value = read_value
    return mock


class TestIsAvailable:
    def test_returns_boolean(self):
        result = is_available()
        assert isinstance(result, bool)


class TestListPorts:
    def test_returns_list(self):
        result = list_ports()
        assert isinstance(result, list)


class TestStatusPyserialUnavailable:
    @patch("app.services.scale_service.HAS_PYSERIAL", False)
    def test_status_code_pyserial_unavailable(self):
        svc = ScaleService()
        status = svc.get_status()
        assert status["pyserial_available"] is False
        assert status["code"] == STATUS_PYSERIAL_UNAVAILABLE
        assert "instalado" in status["message"].lower()

    @patch("app.services.scale_service.HAS_PYSERIAL", False)
    def test_connect_raises_with_code(self):
        svc = ScaleService()
        with pytest.raises(ScaleUnavailableError):
            svc.connect(_make_config())
        status = svc.get_status()
        assert status["code"] == STATUS_PYSERIAL_UNAVAILABLE


class TestStatusNoSerialPorts:
    @patch("app.services.scale_service.HAS_PYSERIAL", True)
    @patch("app.services.scale_service.list_ports", return_value=[])
    def test_code_no_serial_ports(self, mock_lp):
        svc = ScaleService()
        status = svc.get_status()
        assert status["pyserial_available"] is True
        assert status["ports_available"] is False
        assert status["code"] == STATUS_NO_SERIAL_PORTS
        assert "puertos" in status["message"].lower()

    @patch("app.services.scale_service.HAS_PYSERIAL", True)
    @patch("app.services.scale_service.list_ports", return_value=[])
    def test_not_pyserial_unavailable_when_empty(self, mock_lp):
        svc = ScaleService()
        status = svc.get_status()
        assert status["code"] != STATUS_PYSERIAL_UNAVAILABLE


class TestStatusPortsAvailable:
    @patch("app.services.scale_service.HAS_PYSERIAL", True)
    @patch("app.services.scale_service.list_ports", return_value=[{"device": "COM7", "name": "COM7", "description": "USB Serial"}])
    def test_code_scale_not_connected(self, mock_lp):
        svc = ScaleService()
        status = svc.get_status()
        assert status["ports_available"] is True
        assert status["code"] == STATUS_SCALE_NOT_CONNECTED
        assert "conectado" not in status["message"].lower() or "no se ha" in status["message"].lower()


class TestStatusConnected:
    @patch("app.services.scale_service.HAS_PYSERIAL", True)
    @patch("app.services.scale_service.serial")
    def test_code_connected(self, mock_serial_module):
        mock_serial = _make_mock_serial()
        mock_serial_module.Serial.return_value = mock_serial
        mock_serial_module.SerialException = Exception

        svc = ScaleService()
        svc.connect(_make_config("COM3"))
        status = svc.get_status()
        assert status["connected"] is True
        assert status["code"] == STATUS_CONNECTED
        assert "conectada" in status["message"].lower()

        svc.stop()


class TestStatusPortInUse:
    @patch("app.services.scale_service.HAS_PYSERIAL", True)
    @patch("app.services.scale_service.serial")
    def test_code_port_in_use_on_serial_exception(self, mock_serial_module):
        mock_serial_module.Serial.side_effect = Exception("Permission denied")
        mock_serial_module.SerialException = Exception

        svc = ScaleService()
        with pytest.raises(ScaleConnectionError):
            svc.connect(_make_config("COM3"))
        status = svc.get_status()
        assert status["code"] == STATUS_PORT_IN_USE


class TestStatusFields:
    @patch("app.services.scale_service.HAS_PYSERIAL", True)
    @patch("app.services.scale_service.list_ports", return_value=[])
    def test_all_required_fields(self, mock_lp):
        svc = ScaleService()
        status = svc.get_status()
        assert "pyserial_available" in status
        assert "ports_available" in status
        assert "connected" in status
        assert "code" in status
        assert "message" in status
        assert "port" in status
        assert "connected_at" in status
        assert "last_reading" in status
        assert "diagnostic_mode" in status
        assert "error" in status
        assert "reconnect_attempts" in status

    def test_status_types(self):
        svc = ScaleService()
        status = svc.get_status()
        assert isinstance(status["pyserial_available"], bool)
        assert isinstance(status["ports_available"], bool)
        assert isinstance(status["connected"], bool)
        assert isinstance(status["code"], str)
        assert isinstance(status["message"], str)


class TestScaleServiceConnect:
    @patch("app.services.scale_service.HAS_PYSERIAL", True)
    @patch("app.services.scale_service.serial")
    def test_connect_opens_port(self, mock_serial_module):
        mock_serial = _make_mock_serial()
        mock_serial_module.Serial.return_value = mock_serial
        mock_serial_module.SerialException = Exception

        svc = ScaleService()
        config = _make_config()
        svc.connect(config)

        assert svc.connected
        assert svc.port_name == "COM7"
        mock_serial_module.Serial.assert_called_once()

        svc.stop()

    @patch("app.services.scale_service.HAS_PYSERIAL", False)
    def test_connect_no_pyserial_raises(self):
        svc = ScaleService()
        with pytest.raises(ScaleUnavailableError):
            svc.connect(_make_config())

    @patch("app.services.scale_service.HAS_PYSERIAL", True)
    @patch("app.services.scale_service.serial")
    def test_connect_serial_error(self, mock_serial_module):
        mock_serial_module.Serial.side_effect = Exception("Port not found")
        mock_serial_module.SerialException = Exception

        svc = ScaleService()
        with pytest.raises(ScaleConnectionError):
            svc.connect(_make_config())

    @patch("app.services.scale_service.HAS_PYSERIAL", True)
    def test_connect_invalid_port_name(self):
        svc = ScaleService()
        config = _make_config(port="")
        with pytest.raises(ScaleConnectionError):
            svc.connect(config)


class TestScaleServiceDisconnect:
    @patch("app.services.scale_service.HAS_PYSERIAL", True)
    @patch("app.services.scale_service.serial")
    def test_disconnect_closes_port(self, mock_serial_module):
        mock_serial = _make_mock_serial()
        mock_serial_module.Serial.return_value = mock_serial
        mock_serial_module.SerialException = Exception

        svc = ScaleService()
        svc.connect(_make_config())
        assert svc.connected

        svc.disconnect()
        assert not svc.connected

    def test_disconnect_when_not_connected(self):
        svc = ScaleService()
        svc.disconnect()
        assert not svc.connected


class TestScaleServiceDiagnostic:
    def test_toggle_diagnostic(self):
        svc = ScaleService()
        assert svc.diagnostic_mode is False
        svc.set_diagnostic_mode(True)
        assert svc.diagnostic_mode is True
        svc.set_diagnostic_mode(False)
        assert svc.diagnostic_mode is False

    def test_clear_raw_lines_on_disable(self):
        svc = ScaleService()
        svc._last_raw_lines = [{"raw": "test"}]
        svc.set_diagnostic_mode(True)
        svc.set_diagnostic_mode(False)
        assert svc.raw_lines == []


class TestScaleServiceReading:
    def test_last_reading_initially_none(self):
        svc = ScaleService()
        assert svc.last_reading is None

    def test_clear_last_reading(self):
        svc = ScaleService()
        svc._last_reading = WeightReading(
            weight_kg=Decimal("5.000"),
            stable=True,
            unit="kg",
            raw_line="5.000 kg",
            received_at=datetime.now(timezone.utc),
            source_port="COM7",
        )
        svc.clear_last_reading()
        assert svc.last_reading is None


class TestScaleServiceStop:
    def test_stop_disconnects(self):
        svc = ScaleService()
        svc.stop()
        assert not svc.connected

    @patch("app.services.scale_service.HAS_PYSERIAL", True)
    @patch("app.services.scale_service.serial")
    def test_stop_after_connect(self, mock_serial_module):
        mock_serial = _make_mock_serial()
        mock_serial_module.Serial.return_value = mock_serial
        mock_serial_module.SerialException = Exception

        svc = ScaleService()
        svc.connect(_make_config())
        svc.stop()
        assert not svc.connected


class TestScaleServiceSingleton:
    def test_get_returns_same_instance(self):
        s1 = get_scale_service()
        s2 = get_scale_service()
        assert s1 is s2

    def test_reset_creates_new(self):
        s1 = get_scale_service()
        reset_scale_service()
        s2 = get_scale_service()
        assert s1 is not s2
