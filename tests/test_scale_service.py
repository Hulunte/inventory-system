"""Tests for scale service (mocked serial)."""
import threading
import time
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


class TestScaleServiceStatus:
    def test_status_when_disconnected(self):
        svc = ScaleService()
        status = svc.get_status()
        assert status["connected"] is False
        assert status["port"] == ""
        assert status["last_reading"] is None

    @patch("app.services.scale_service.HAS_PYSERIAL", True)
    @patch("app.services.scale_service.serial")
    def test_status_when_connected(self, mock_serial_module):
        mock_serial = _make_mock_serial()
        mock_serial_module.Serial.return_value = mock_serial
        mock_serial_module.SerialException = Exception

        svc = ScaleService()
        svc.connect(_make_config("COM3"))
        status = svc.get_status()
        assert status["connected"] is True
        assert status["port"] == "COM3"

        svc.stop()


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
