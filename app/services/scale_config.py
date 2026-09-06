"""Scale configuration management.

Validates and provides access to SCALE_* environment variables.
No serial connections are opened during import or app startup.
"""

import os
from dataclasses import dataclass

DEFAULT_BAUDRATE = 9600
DEFAULT_BYTESIZE = 8
DEFAULT_PARITY = "N"
DEFAULT_STOPBITS = 1
DEFAULT_TIMEOUT_SECONDS = 1.0
DEFAULT_LINE_ENCODING = "ascii"
DEFAULT_PROFILE = "auto"
DEFAULT_MIN_WEIGHT_KG = "0.001"
DEFAULT_MAX_WEIGHT_KG = "999.999"

VALID_PARITIES = {"N", "E", "O", "M", "S"}
VALID_PROFILES = {"auto", "torrey", "generic", "raw"}


@dataclass(frozen=True)
class ScaleConfig:
    port: str
    baudrate: int
    bytesize: int
    parity: str
    stopbits: float
    timeout_seconds: float
    line_encoding: str
    profile: str
    min_weight_kg: str
    max_weight_kg: str

    @property
    def parity_int(self):
        return {
            "N": 0,  # serial.PARITY_NONE
            "E": 2,  # serial.PARITY_EVEN
            "O": 1,  # serial.PARITY_ODD
            "M": 3,  # serial.PARITY_MARK
            "S": 4,  # serial.PARITY_SPACE
        }[self.parity]

    @property
    def stopbits_float(self):
        return self.stopbits


def load_scale_config() -> ScaleConfig:
    """Load scale configuration from environment variables.

    Returns a ScaleConfig with validated values.
    Raises ValueError for invalid configuration.
    """
    port = os.getenv("SCALE_PORT", "").strip()
    if not port:
        raise ValueError("SCALE_PORT is required")

    baudrate = _parse_int("SCALE_BAUDRATE", os.getenv("SCALE_BAUDRATE", ""), DEFAULT_BAUDRATE)
    if baudrate not in (300, 600, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200):
        raise ValueError(f"SCALE_BAUDRATE invalid: {baudrate}")

    bytesize = _parse_int("SCALE_BYTESIZE", os.getenv("SCALE_BYTESIZE", ""), DEFAULT_BYTESIZE)
    if bytesize not in (5, 6, 7, 8):
        raise ValueError(f"SCALE_BYTESIZE invalid: {bytesize}")

    parity = os.getenv("SCALE_PARITY", DEFAULT_PARITY).strip().upper()
    if parity not in VALID_PARITIES:
        raise ValueError(f"SCALE_PARITY invalid: {parity}. Use one of {VALID_PARITIES}")

    stopbits = _parse_float("SCALE_STOPBITS", os.getenv("SCALE_STOPBITS", ""), float(DEFAULT_STOPBITS))
    if stopbits not in (1.0, 1.5, 2.0):
        raise ValueError(f"SCALE_STOPBITS invalid: {stopbits}. Use 1, 1.5, or 2")

    timeout_seconds = _parse_float(
        "SCALE_TIMEOUT_SECONDS",
        os.getenv("SCALE_TIMEOUT_SECONDS", ""),
        DEFAULT_TIMEOUT_SECONDS,
    )
    if timeout_seconds <= 0:
        raise ValueError(f"SCALE_TIMEOUT_SECONDS must be positive: {timeout_seconds}")

    line_encoding = os.getenv("SCALE_LINE_ENCODING", DEFAULT_LINE_ENCODING).strip().lower()
    try:
        "test".encode(line_encoding)
    except (LookupError, UnicodeError):
        raise ValueError(f"SCALE_LINE_ENCODING invalid: {line_encoding}")

    profile = os.getenv("SCALE_PROFILE", DEFAULT_PROFILE).strip().lower()
    if profile not in VALID_PROFILES:
        raise ValueError(f"SCALE_PROFILE invalid: {profile}. Use one of {VALID_PROFILES}")

    min_weight = os.getenv("SCALE_MIN_WEIGHT_KG", DEFAULT_MIN_WEIGHT_KG).strip()
    max_weight = os.getenv("SCALE_MAX_WEIGHT_KG", DEFAULT_MAX_WEIGHT_KG).strip()
    _validate_weight_range(min_weight, max_weight)

    return ScaleConfig(
        port=port,
        baudrate=baudrate,
        bytesize=bytesize,
        parity=parity,
        stopbits=stopbits,
        timeout_seconds=timeout_seconds,
        line_encoding=line_encoding,
        profile=profile,
        min_weight_kg=min_weight,
        max_weight_kg=max_weight,
    )


def validate_port_name(port: str) -> bool:
    """Validate that a port name is safe to use."""
    if not port or not isinstance(port, str):
        return False
    port = port.strip()
    if len(port) > 50:
        return False
    if any(c in port for c in ("\x00", "\n", "\r")):
        return False
    return True


def _parse_int(name, value, default):
    if not value:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        raise ValueError(f"{name} must be an integer: {value!r}")


def _parse_float(name, value, default):
    if not value:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        raise ValueError(f"{name} must be a number: {value!r}")


def _validate_weight_range(min_str, max_str):
    from decimal import Decimal

    try:
        min_d = Decimal(min_str)
        max_d = Decimal(max_str)
    except Exception:
        raise ValueError(f"Invalid weight range: {min_str!r} - {max_str!r}")

    if min_d < 0:
        raise ValueError(f"SCALE_MIN_WEIGHT_KG must not be negative: {min_str}")
    if max_d <= min_d:
        raise ValueError(f"SCALE_MAX_WEIGHT_KG must be greater than SCALE_MIN_WEIGHT_KG")
