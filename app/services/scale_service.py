"""Scale serial connection service.

Manages serial port connections, background reading, and state.
Uses pyserial if available; degrades gracefully if not.
No Flask import at module level.
"""

import logging
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from app.services.scale_config import ScaleConfig, validate_port_name
from app.services.scale_parser import WeightReading, parse_weight_line, sanitize_for_display

logger = logging.getLogger(__name__)

try:
    import serial
    import serial.tools.list_ports
    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False
    serial = None

MAX_RAW_LOG = 50
RECONNECT_DELAY = 2.0
MAX_RECONNECT_ATTEMPTS = 5


class ScaleError(Exception):
    pass


class ScaleUnavailableError(ScaleError):
    pass


class ScaleConnectionError(ScaleError):
    pass


def is_available() -> bool:
    return HAS_PYSERIAL


def list_ports():
    """List available serial ports.

    Returns list of dicts with name, device, description.
    """
    if not HAS_PYSERIAL:
        return []
    try:
        ports = serial.tools.list_ports.comports()
        return [
            {
                "name": p.device,
                "device": p.device,
                "description": p.description or "Unknown",
            }
            for p in ports
        ]
    except Exception:
        return []


def validate_port_exists(port_name: str) -> bool:
    """Check if a port exists on the system."""
    if not HAS_PYSERIAL:
        return False
    if not validate_port_name(port_name):
        return False
    try:
        ports = list_ports()
        return any(p["device"] == port_name for p in ports)
    except Exception:
        return False


class ScaleService:
    """Manages a single serial scale connection with background reading."""

    def __init__(self):
        self._lock = threading.Lock()
        self._serial: Optional[object] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._port_name: str = ""
        self._config: Optional[ScaleConfig] = None
        self._last_reading: Optional[WeightReading] = None
        self._last_raw_lines: list = []
        self._diagnostic_mode = False
        self._reconnect_attempts = 0
        self._connected_at: Optional[datetime] = None
        self._error: Optional[str] = None

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._serial is not None and self._serial.is_open

    @property
    def port_name(self) -> str:
        return self._port_name

    @property
    def last_reading(self) -> Optional[WeightReading]:
        return self._last_reading

    @property
    def last_error(self) -> Optional[str]:
        return self._error

    @property
    def connected_at(self) -> Optional[datetime]:
        return self._connected_at

    @property
    def diagnostic_mode(self) -> bool:
        return self._diagnostic_mode

    @property
    def raw_lines(self) -> list:
        with self._lock:
            return list(self._last_raw_lines)

    def connect(self, config: ScaleConfig) -> None:
        """Open serial connection and start background reading."""
        if not HAS_PYSERIAL:
            raise ScaleUnavailableError(
                "Lectura de bascula no disponible. Instale pyserial."
            )

        if not validate_port_name(config.port):
            raise ScaleConnectionError("Nombre de puerto invalido")

        with self._lock:
            if self._serial and self._serial.is_open:
                self._close_internal()

        try:
            ser = serial.Serial(
                port=config.port,
                baudrate=config.baudrate,
                bytesize=config.bytesize,
                parity=config.parity,
                stopbits=config.stopbits,
                timeout=config.timeout_seconds,
            )
        except serial.SerialException as e:
            self._error = f"Error al abrir {config.port}: {e}"
            raise ScaleConnectionError(self._error) from e
        except Exception as e:
            self._error = f"Error inesperado al abrir {config.port}: {e}"
            raise ScaleConnectionError(self._error) from e

        with self._lock:
            self._serial = ser
            self._port_name = config.port
            self._config = config
            self._error = None
            self._connected_at = datetime.now(timezone.utc)
            self._reconnect_attempts = 0

        self._start_reader()
        logger.info("Connected to scale on %s", config.port)

    def disconnect(self) -> None:
        """Stop reading and close the serial connection."""
        self._stop_reader()
        with self._lock:
            self._close_internal()
        logger.info("Disconnected from scale")

    def get_status(self) -> dict:
        """Get current connection status."""
        reading_dict = None
        if self._last_reading:
            reading_dict = self._last_reading.to_dict()

        return {
            "available": HAS_PYSERIAL,
            "connected": self.connected,
            "port": self._port_name,
            "connected_at": self._connected_at.isoformat() if self._connected_at else None,
            "last_reading": reading_dict,
            "diagnostic_mode": self._diagnostic_mode,
            "error": self._error,
            "reconnect_attempts": self._reconnect_attempts,
        }

    def set_diagnostic_mode(self, enabled: bool) -> None:
        self._diagnostic_mode = enabled
        if not enabled:
            with self._lock:
                self._last_raw_lines.clear()

    def clear_last_reading(self) -> None:
        self._last_reading = None

    def stop(self) -> None:
        """Explicitly stop the service."""
        self.disconnect()

    def _start_reader(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._read_loop, daemon=True, name="scale-reader"
        )
        self._thread.start()

    def _stop_reader(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

    def _read_loop(self) -> None:
        while self._running:
            try:
                self._read_once()
            except Exception as e:
                logger.debug("Read error: %s", e)
                self._error = str(e)
                self._attempt_reconnect()

    def _read_once(self) -> None:
        ser = self._serial
        if not ser or not ser.is_open:
            time.sleep(0.1)
            return

        try:
            raw = ser.readline()
        except serial.SerialException as e:
            raise ScaleConnectionError(str(e)) from e

        if not raw:
            return

        config = self._config
        if not config:
            return

        timestamp = datetime.now(timezone.utc)

        try:
            reading = parse_weight_line(
                raw_line=raw,
                source_port=self._port_name,
                min_weight_kg=config.min_weight_kg,
                max_weight_kg=config.max_weight_kg,
                line_encoding=config.line_encoding,
                timestamp=timestamp,
            )
        except Exception as e:
            logger.debug("Parse error: %s", e)
            return

        if self._diagnostic_mode:
            display = sanitize_for_display(
                raw if isinstance(raw, str) else raw.decode(config.line_encoding, errors="replace")
            )
            with self._lock:
                self._last_raw_lines.append({
                    "raw": display,
                    "timestamp": timestamp.isoformat(),
                    "parsed_ok": reading.ok,
                })
                if len(self._last_raw_lines) > MAX_RAW_LOG:
                    self._last_raw_lines.pop(0)

        if reading.ok:
            self._last_reading = reading
            self._error = None
            self._reconnect_attempts = 0

    def _attempt_reconnect(self) -> None:
        if not self._running:
            return
        if self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            self._error = "Maximo numero de reconexiones alcanzado"
            self._running = False
            return

        self._reconnect_attempts += 1
        config = self._config
        if not config:
            self._running = False
            return

        self._stop_reader()
        with self._lock:
            self._close_internal()

        time.sleep(RECONNECT_DELAY)

        if not self._running:
            return

        try:
            ser = serial.Serial(
                port=config.port,
                baudrate=config.baudrate,
                bytesize=config.bytesize,
                parity=config.parity,
                stopbits=config.stopbits,
                timeout=config.timeout_seconds,
            )
            with self._lock:
                self._serial = ser
                self._error = None
            logger.info("Reconnected to scale on %s", config.port)
        except Exception as e:
            self._error = f"Reconexion fallida: {e}"
            logger.debug("Reconnect failed: %s", e)

    def _close_internal(self) -> None:
        """Close serial port without locking (caller must hold lock)."""
        if self._serial:
            try:
                if self._serial.is_open:
                    self._serial.close()
            except Exception:
                pass
            self._serial = None


_scale_service: Optional[ScaleService] = None
_service_lock = threading.Lock()


def get_scale_service() -> ScaleService:
    """Get or create the global scale service singleton."""
    global _scale_service
    with _service_lock:
        if _scale_service is None:
            _scale_service = ScaleService()
        return _scale_service


def reset_scale_service() -> None:
    """Reset the global scale service (for testing)."""
    global _scale_service
    with _service_lock:
        if _scale_service:
            _scale_service.stop()
        _scale_service = None
