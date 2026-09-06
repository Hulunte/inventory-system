"""Pure weight parser for scale readings.

No Flask dependency. No serial dependency.
Supports configurable profiles and common formats.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional


@dataclass(frozen=True)
class WeightReading:
    """Parsed weight reading from a scale."""
    weight_kg: Decimal
    stable: bool
    unit: str
    raw_line: str
    received_at: datetime
    source_port: str
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self):
        return {
            "weight_kg": str(self.weight_kg),
            "stable": self.stable,
            "unit": self.unit,
            "raw_line": self.raw_line,
            "received_at": self.received_at.isoformat(),
            "source_port": self.source_port,
            "error": self.error,
        }


STABILITY_PREFIXES = ("ST", "US", "GS", "NT", "SW", "STB", "STAB")
STABILITY_SUFFIXES = ("ST", "US", "GS", "NT")

UNIT_KNOWN = ("kg", "g", "lb", "lbs", "oz")

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0e-\x1f\x7f]")

_WEIGHT_RE = re.compile(
    r"([+-]?\d+(?:[.,]\d+)?)\s*(kg|g|lb|lbs|oz)?",
    re.IGNORECASE,
)

_NAN_INF_RE = re.compile(
    r"[+-]?\s*(NaN|Inf(?:inity)?|INF)",
    re.IGNORECASE,
)


def parse_weight_line(
    raw_line: str,
    source_port: str = "",
    min_weight_kg: str = "0.001",
    max_weight_kg: str = "999.999",
    line_encoding: str = "ascii",
    max_decimals: int = 3,
    timestamp: Optional[datetime] = None,
) -> WeightReading:
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    sanitized = _sanitize_line(raw_line, line_encoding)

    if not sanitized:
        return _error(raw_line, "empty_line", source_port, timestamp)

    stable = _detect_stability(sanitized)
    cleaned = _strip_stability_markers(sanitized)

    if _NAN_INF_RE.search(cleaned):
        return _error(raw_line, "nan_or_infinity", source_port, timestamp)

    unit = _detect_unit(cleaned)
    numeric_str = _extract_numeric(cleaned)

    if numeric_str is None:
        return _error(raw_line, "no_numeric_value", source_port, timestamp)

    try:
        weight = Decimal(numeric_str)
    except InvalidOperation:
        return _error(raw_line, "invalid_decimal", source_port, timestamp)

    if weight < 0:
        return _error(raw_line, "negative_weight", source_port, timestamp)

    if weight == 0:
        return _error(raw_line, "zero_weight", source_port, timestamp)

    if _too_many_decimals(weight, max_decimals):
        return _error(raw_line, "too_many_decimals", source_port, timestamp)

    if unit == "g":
        weight = weight / Decimal("1000")
        unit = "kg"
    elif unit in ("lb", "lbs"):
        weight = weight * Decimal("0.45359237")
        unit = "kg"
    elif unit == "oz":
        weight = weight * Decimal("0.028349523125")
        unit = "kg"
    elif unit == "":
        unit = "kg"
    # "kg" already correct, no conversion needed

    min_d = _safe_decimal(min_weight_kg, Decimal("0.001"))
    max_d = _safe_decimal(max_weight_kg, Decimal("999.999"))

    if weight < min_d:
        return _error(raw_line, "weight_below_minimum", source_port, timestamp)

    if weight > max_d:
        return _error(raw_line, "weight_above_maximum", source_port, timestamp)

    return WeightReading(
        weight_kg=weight.quantize(Decimal("0.001")),
        stable=stable,
        unit=unit,
        raw_line=sanitized,
        received_at=timestamp,
        source_port=source_port,
    )


def sanitize_for_display(raw_line: str, max_length: int = 200) -> str:
    if not raw_line:
        return ""
    result = raw_line
    result = _CONTROL_CHAR_RE.sub(".", result)
    result = result.replace("<", ".").replace(">", ".")
    if len(result) > max_length:
        result = result[:max_length] + "..."
    return result


def _sanitize_line(raw_line: str, encoding: str) -> str:
    if not raw_line:
        return ""
    text = raw_line
    if isinstance(text, bytes):
        try:
            text = text.decode(encoding, errors="replace")
        except (LookupError, UnicodeError):
            text = text.decode("ascii", errors="replace")
    text = text.strip("\r\n\x00\x04\x03")
    text = _CONTROL_CHAR_RE.sub("", text)
    return text.strip()


def _detect_stability(text: str) -> bool:
    upper = text.upper()
    for prefix in STABILITY_PREFIXES:
        if upper.startswith(prefix + " ") or upper.startswith(prefix + "\t"):
            return True
    for suffix in STABILITY_SUFFIXES:
        if upper.endswith(" " + suffix) or upper.endswith("\t" + suffix):
            return True
    return False


def _strip_stability_markers(text: str) -> str:
    upper = text.upper()
    result = text
    for prefix in sorted(STABILITY_PREFIXES, key=len, reverse=True):
        if upper.startswith(prefix + " ") or upper.startswith(prefix + "\t"):
            result = result[len(prefix):].lstrip()
            upper = result.upper()
            break
    for suffix in sorted(STABILITY_SUFFIXES, key=len, reverse=True):
        if upper.endswith(" " + suffix) or upper.endswith("\t" + suffix):
            result = result[: -len(suffix) - 1].rstrip()
            break
    return result


def _detect_unit(text: str) -> str:
    upper = text.upper()
    for unit in sorted(UNIT_KNOWN, key=len, reverse=True):
        if unit.upper() in upper:
            return unit
    return ""


def _extract_numeric(text: str) -> Optional[str]:
    match = _WEIGHT_RE.search(text)
    if not match:
        return None
    num_str = match.group(1)
    num_str = num_str.replace(",", ".")
    return num_str


def _too_many_decimals(weight: Decimal, max_decimals: int) -> bool:
    if weight == 0:
        return False
    tup = weight.as_tuple()
    if hasattr(tup, "exponent") and tup.exponent < 0:
        return abs(tup.exponent) > max_decimals
    return False


def _safe_decimal(s: str, default: Decimal) -> Decimal:
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError, TypeError):
        return default


def _error(raw_line, error_code, source_port, timestamp) -> WeightReading:
    return WeightReading(
        weight_kg=Decimal("0"),
        stable=False,
        unit="",
        raw_line=raw_line or "",
        received_at=timestamp,
        source_port=source_port,
        error=error_code,
    )
