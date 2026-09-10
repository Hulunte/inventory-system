"""Scale serial connection service.

Manages serial port connections, background reading, and state.
Uses pyserial if available; degrades gracefully if not.
No Flask import at module level.
"""

import logging
import platform
import threading
import time
from dataclasses import replace
from datetime import datetime, timezone
from typing import Optional

from app.services.scale_config import ScaleConfig, validate_port_name
from app.services.scale_parser import WeightReading, parse_weight_line, sanitize_for_display

logger = logging.getLogger(__name__)

HAS_PYSERIAL = False
serial = None
serial_list_ports = None

try:
    import serial as _serial
    import serial.tools.list_ports as _list_ports
    serial = _serial
    serial_list_ports = _list_ports
    HAS_PYSERIAL = True
except ImportError:
    pass
except Exception:
    pass

MAX_RAW_LOG = 50
MAX_FRAME_BUFFER = 4096
RECONNECT_DELAY = 2.0
MAX_RECONNECT_ATTEMPTS = 5
AUTO_REQUEST_INTERVAL_SECONDS = 0.75
STABLE_MATCH_COUNT = 2
STABILITY_MAX_GAP_SECONDS = 2.0

STATUS_CONNECTED = "connected"
STATUS_NO_SERIAL_PORTS = "no_serial_ports"
STATUS_SCALE_NOT_CONNECTED = "scale_not_connected"
STATUS_PORT_IN_USE = "port_in_use"
STATUS_INVALID_CONFIGURATION = "invalid_configuration"
STATUS_SERIAL_READ_ERROR = "serial_read_error"
STATUS_UNSUPPORTED_PLATFORM = "unsupported_platform"
STATUS_PYSERIAL_UNAVAILABLE = "pyserial_unavailable"


class ScaleError(Exception):
    pass


class ScaleUnavailableError(ScaleError):
    pass


class ScaleConnectionError(ScaleError):
    pass


def is_available() -> bool:
    return HAS_PYSERIAL


def list_ports(*, raise_errors=False):
    """List available serial ports.

    Returns list of dicts with name, device, description.
    Empty list when no ports found or PySerial unavailable.
    """
    if not HAS_PYSERIAL:
        return []
    try:
        ports = serial_list_ports.comports()
        return [
            {
                "name": p.device,
                "device": p.device,
                "description": p.description or "Unknown",
            }
            for p in ports
        ]
    except Exception:
        if raise_errors:
            raise
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


def _get_status_code_and_message(connected: bool, port: str) -> tuple:
    """Determine status code and human-readable message."""
    if not HAS_PYSERIAL:
        return STATUS_PYSERIAL_UNAVAILABLE, (
            "El componente serial no esta instalado."
        )

    if platform.system() not in ("Windows", "Linux", "Darwin"):
        return STATUS_UNSUPPORTED_PLATFORM, (
            "Plataforma no soportada para lectura serial."
        )

    if connected:
        return STATUS_CONNECTED, "Bascula conectada."

    ports = list_ports()
    if not ports:
        return STATUS_NO_SERIAL_PORTS, (
            "No hay puertos seriales disponibles. "
            "Conecte la bascula y actualice."
        )

    return STATUS_SCALE_NOT_CONNECTED, (
        "Hay puertos disponibles, pero no se ha conectado una bascula."
    )


class ScaleService:
    """Manages a single serial scale connection with background reading."""

    def __init__(self):
        self._lock = threading.Lock()
        self._serial: Optional[object] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()
        self._read_buffer = bytearray()
        self._port_name: str = ""
        self._config: Optional[ScaleConfig] = None
        self._last_reading: Optional[WeightReading] = None
        self._last_raw_lines: list = []
        self._diagnostic_mode = False
        self._reconnect_attempts = 0
        self._connected_at: Optional[datetime] = None
        self._error: Optional[str] = None
        self._status_code: str = STATUS_SCALE_NOT_CONNECTED
        self._automatic_read = False
        self._last_request_monotonic = 0.0
        self._last_request_at: Optional[datetime] = None
        self._stability_candidate = None
        self._stability_match_count = 0
        self._stability_candidate_at: Optional[datetime] = None

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
            self._status_code = STATUS_PYSERIAL_UNAVAILABLE
            raise ScaleUnavailableError(
                "El componente serial no esta instalado."
            )

        if not validate_port_name(config.port):
            self._status_code = STATUS_INVALID_CONFIGURATION
            raise ScaleConnectionError("Nombre de puerto invalido")

        with self._lock:
            if self._serial and self._serial.is_open:
                raise ScaleConnectionError(
                    f"Ya existe una conexion activa en {self._port_name}."
                )

        try:
            ser = serial.Serial(
                port=config.port,
                baudrate=config.baudrate,
                bytesize=config.bytesize,
                parity=config.parity,
                stopbits=config.stopbits,
                timeout=config.timeout_seconds,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
            # Match .NET SerialPort defaults used by the working tester when
            # Handshake=None: do not assert hardware control lines.
            ser.dtr = False
            ser.rts = False
        except serial.SerialException as e:
            self._error = f"Error al abrir {config.port}: {e}"
            self._status_code = STATUS_PORT_IN_USE
            raise ScaleConnectionError(self._error) from e
        except Exception as e:
            self._error = f"Error inesperado al abrir {config.port}: {e}"
            self._status_code = STATUS_INVALID_CONFIGURATION
            raise ScaleConnectionError(self._error) from e

        with self._lock:
            self._serial = ser
            self._port_name = config.port
            self._config = config
            self._error = None
            self._connected_at = datetime.now(timezone.utc)
            self._reconnect_attempts = 0
            self._status_code = STATUS_CONNECTED
            self._read_buffer.clear()
            self._reset_stability_tracking()

        self._start_reader()
        logger.info(
            "Connected to scale on %s (%s baud, %s%s%s, handshake=%s, "
            "encoding=%s, terminator=%s, profile=%s)",
            config.port,
            config.baudrate,
            config.bytesize,
            config.parity,
            config.stopbits,
            config.handshake,
            config.line_encoding,
            config.terminator,
            config.profile,
        )

    def disconnect(self) -> None:
        """Stop reading and close the serial connection."""
        self._running = False
        self._stop_event.set()
        with self._lock:
            self._close_internal()
        self._stop_reader()
        with self._lock:
            self._port_name = ""
            self._config = None
            self._connected_at = None
            self._last_reading = None
            self._read_buffer.clear()
            self._error = None
            self._reconnect_attempts = 0
            self._automatic_read = False
            self._last_request_at = None
            self._last_request_monotonic = 0.0
            self._reset_stability_tracking()
        self._status_code = _get_status_code_and_message(False, self._port_name)[0]
        logger.info("Disconnected from scale")

    def get_status(self) -> dict:
        """Get current connection status with code and message."""
        reading_dict = None
        if self._last_reading:
            reading_dict = self._last_reading.to_dict()

        is_conn = self.connected

        if is_conn:
            code = STATUS_CONNECTED
            message = "Bascula conectada."
        elif self._error and self._status_code in (
            STATUS_PORT_IN_USE, STATUS_INVALID_CONFIGURATION, STATUS_SERIAL_READ_ERROR,
        ):
            code = self._status_code
            message = self._error
        elif self._error and self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            code = STATUS_SERIAL_READ_ERROR
            message = "Error de lectura serial persistente."
        else:
            code, message = _get_status_code_and_message(is_conn, self._port_name)

        return {
            "pyserial_available": HAS_PYSERIAL,
            "ports_available": bool(list_ports()),
            "connected": is_conn,
            "code": code,
            "message": message,
            "port": self._port_name,
            "connected_at": self._connected_at.isoformat() if self._connected_at else None,
            "last_reading": reading_dict,
            "diagnostic_mode": self._diagnostic_mode,
            "error": self._error,
            "reconnect_attempts": self._reconnect_attempts,
            "automatic_read": self._automatic_read,
            "last_request_at": self._last_request_at.isoformat() if self._last_request_at else None,
        }

    def set_diagnostic_mode(self, enabled: bool) -> None:
        self._diagnostic_mode = enabled
        if not enabled:
            with self._lock:
                self._last_raw_lines.clear()

    def clear_last_reading(self) -> None:
        self._last_reading = None
        self._reset_stability_tracking()

    def _reset_stability_tracking(self) -> None:
        self._stability_candidate = None
        self._stability_match_count = 0
        self._stability_candidate_at = None

    def _resolve_stability(self, reading: WeightReading) -> WeightReading:
        """Infer Torrey stability when GenericAscii omits an ST marker."""
        if reading.stable:
            self._stability_candidate = reading.weight_kg
            self._stability_match_count = STABLE_MATCH_COUNT
            self._stability_candidate_at = reading.received_at
            return reading

        previous_at = self._stability_candidate_at
        within_gap = (
            previous_at is not None
            and 0 <= (reading.received_at - previous_at).total_seconds()
            <= STABILITY_MAX_GAP_SECONDS
        )
        if reading.weight_kg == self._stability_candidate and within_gap:
            self._stability_match_count += 1
        else:
            self._stability_candidate = reading.weight_kg
            self._stability_match_count = 1
        self._stability_candidate_at = reading.received_at
        if self._stability_match_count >= STABLE_MATCH_COUNT:
            return replace(reading, stable=True)
        return reading

    def set_automatic_read(self, enabled: bool) -> None:
        self._automatic_read = bool(enabled)
        self._last_request_monotonic = 0.0

    def request_weight(self) -> None:
        """Send one Torrey GenericAscii weight request (ASCII W / 0x57)."""
        with self._lock:
            ser = self._serial
            if ser is None or not ser.is_open:
                raise ScaleConnectionError("No hay conexion activa")
            try:
                ser.write(b"W")
                ser.flush()
            except serial.SerialException as e:
                raise ScaleConnectionError(str(e)) from e
        self._last_request_monotonic = time.monotonic()
        self._last_request_at = datetime.now(timezone.utc)
        if self._diagnostic_mode:
            logger.info("Scale diagnostic TX port=%s bytes=57 text='W'", self._port_name)

    def stop(self) -> None:
        """Explicitly stop the service."""
        self.disconnect()

    def _start_reader(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._read_loop, daemon=True, name="scale-reader"
        )
        self._thread.start()

    def _stop_reader(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=3.0)
        self._thread = None

    def _read_loop(self) -> None:
        while self._running and not self._stop_event.is_set():
            try:
                if (
                    self._automatic_read
                    and time.monotonic() - self._last_request_monotonic
                    >= AUTO_REQUEST_INTERVAL_SECONDS
                ):
                    self.request_weight()
                self._read_once()
            except ScaleConnectionError:
                self._status_code = STATUS_SERIAL_READ_ERROR
                self._attempt_reconnect()
            except Exception as e:
                logger.debug("Read error: %s", e)
                self._error = str(e)
                self._status_code = STATUS_SERIAL_READ_ERROR
                self._attempt_reconnect()

    def _read_once(self) -> None:
        ser = self._serial
        if not ser or not ser.is_open:
            time.sleep(0.1)
            return

        try:
            waiting = int(getattr(ser, "in_waiting", 0) or 0)
            raw = ser.read(max(1, waiting))
        except serial.SerialException as e:
            raise ScaleConnectionError(str(e)) from e

        if not raw:
            return

        config = self._config
        if not config:
            return

        if isinstance(raw, str):
            raw = raw.encode(config.line_encoding, errors="replace")
        if self._diagnostic_mode:
            self._record_diagnostic(raw, config, kind="chunk")
        self._read_buffer.extend(raw)
        # Torrey devices may emit CR, CRLF, CRCRLF, or deliver the final LF
        # in a later USB chunk. A CR already completes the ASCII weight frame.
        while True:
            indexes = [
                index for index in (
                    self._read_buffer.find(b"\r"),
                    self._read_buffer.find(b"\n"),
                ) if index >= 0
            ]
            if not indexes:
                break
            end = min(indexes)
            frame = bytes(self._read_buffer[:end])
            consume = end
            while consume < len(self._read_buffer) and self._read_buffer[consume] in (10, 13):
                consume += 1
            self._read_buffer = self._read_buffer[consume:]
            if frame.strip():
                self._process_frame(frame, config)

        if len(self._read_buffer) > MAX_FRAME_BUFFER:
            self._diagnose_discard(
                bytes(self._read_buffer),
                "frame_too_long_without_terminator",
                config,
            )
            self._read_buffer.clear()

    def _process_frame(self, raw: bytes, config: ScaleConfig) -> None:
        """Parse one complete serial frame after its configured terminator."""
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
            self._diagnose_discard(raw, f"parser_exception:{type(e).__name__}", config)
            return

        if self._diagnostic_mode:
            display = sanitize_for_display(raw.decode(config.line_encoding, errors="replace"))
            with self._lock:
                self._last_raw_lines.append({
                    "kind": "frame",
                    "raw": display,
                    "hex": raw.hex(" "),
                    "timestamp": timestamp.isoformat(),
                    "parsed_ok": reading.ok,
                    "weight_kg": str(reading.weight_kg) if reading.ok else None,
                    "discard_reason": reading.error,
                })
                if len(self._last_raw_lines) > MAX_RAW_LOG:
                    self._last_raw_lines.pop(0)

        if reading.ok:
            reading = self._resolve_stability(reading)
            self._last_reading = reading
            self._error = None
            self._reconnect_attempts = 0
            if self._diagnostic_mode:
                logger.info(
                    "Scale diagnostic port=%s bytes=%s text=%r parsed_weight_kg=%s stable=%s",
                    self._port_name,
                    raw.hex(" "),
                    display,
                    reading.weight_kg,
                    reading.stable,
                )
        else:
            self._diagnose_discard(raw, reading.error or "unknown_parser_error", config)

    def _diagnose_discard(self, raw: bytes, reason: str, config: ScaleConfig) -> None:
        if not self._diagnostic_mode:
            return
        text = sanitize_for_display(raw.decode(config.line_encoding, errors="replace"))
        logger.info(
            "Scale diagnostic discarded port=%s bytes=%s text=%r reason=%s",
            self._port_name,
            raw.hex(" "),
            text,
            reason,
        )

    def _record_diagnostic(self, raw: bytes, config: ScaleConfig, *, kind: str) -> None:
        text = sanitize_for_display(raw.decode(config.line_encoding, errors="replace"))
        with self._lock:
            self._last_raw_lines.append({
                "kind": kind,
                "raw": text,
                "hex": raw.hex(" "),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "parsed_ok": None,
                "weight_kg": None,
                "discard_reason": None,
            })
            if len(self._last_raw_lines) > MAX_RAW_LOG:
                self._last_raw_lines.pop(0)
        logger.info(
            "Scale diagnostic received port=%s bytes=%s text=%r",
            self._port_name,
            raw.hex(" "),
            text,
        )

    def _attempt_reconnect(self) -> None:
        if not self._running:
            return
        if self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            self._error = "Maximo numero de reconexiones alcanzado"
            self._status_code = STATUS_SERIAL_READ_ERROR
            self._running = False
            return

        self._reconnect_attempts += 1
        config = self._config
        if not config:
            self._running = False
            return

        with self._lock:
            self._close_internal()

        if self._stop_event.wait(RECONNECT_DELAY):
            return

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
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
            ser.dtr = False
            ser.rts = False
            with self._lock:
                self._serial = ser
                self._error = None
            self._status_code = STATUS_CONNECTED
            logger.info("Reconnected to scale on %s", config.port)
        except serial.SerialException as e:
            self._error = f"Reconexion fallida: {e}"
            self._status_code = STATUS_PORT_IN_USE
            logger.debug("Reconnect failed: %s", e)
        except Exception as e:
            self._error = f"Reconexion fallida: {e}"
            self._status_code = STATUS_INVALID_CONFIGURATION
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
