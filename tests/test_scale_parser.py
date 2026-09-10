"""Tests for scale weight parser (pure, no Flask, no serial)."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.scale_parser import (
    WeightReading,
    parse_weight_line,
    sanitize_for_display,
)


FIXED_TS = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)


class TestParseWeightLine:
    def test_basic_kg(self):
        r = parse_weight_line("12.345 kg", timestamp=FIXED_TS)
        assert r.ok
        assert r.weight_kg == Decimal("12.345")
        assert r.unit == "kg"
        assert r.stable is False

    def test_weight_with_point(self):
        r = parse_weight_line("5.500", timestamp=FIXED_TS)
        assert r.ok
        assert r.weight_kg == Decimal("5.500")

    def test_weight_with_comma(self):
        r = parse_weight_line("5,500", timestamp=FIXED_TS)
        assert r.ok
        assert r.weight_kg == Decimal("5.500")

    def test_weight_kg_suffix(self):
        r = parse_weight_line("ST 10.000 kg", timestamp=FIXED_TS)
        assert r.ok
        assert r.weight_kg == Decimal("10.000")
        assert r.stable is True
        assert r.unit == "kg"

    def test_grams_converted_to_kg(self):
        r = parse_weight_line("500 g", timestamp=FIXED_TS)
        assert r.ok
        assert r.weight_kg == Decimal("0.500")
        assert r.unit == "kg"

    def test_pounds_converted_to_kg(self):
        r = parse_weight_line("10.00 lb", timestamp=FIXED_TS)
        assert r.ok
        assert r.weight_kg == Decimal("4.536")
        assert r.unit == "kg"

    def test_stable_prefix_st(self):
        r = parse_weight_line("ST 25.000 kg", timestamp=FIXED_TS)
        assert r.ok
        assert r.stable is True

    def test_stable_prefix_us(self):
        r = parse_weight_line("US 25.000 kg", timestamp=FIXED_TS)
        assert r.ok
        assert r.stable is True

    def test_stable_prefix_gs(self):
        r = parse_weight_line("GS 25.000 kg", timestamp=FIXED_TS)
        assert r.ok
        assert r.stable is True

    def test_stable_prefix_nt(self):
        r = parse_weight_line("NT 25.000 kg", timestamp=FIXED_TS)
        assert r.ok
        assert r.stable is True

    def test_stable_suffix_st(self):
        r = parse_weight_line("25.000 kg ST", timestamp=FIXED_TS)
        assert r.ok
        assert r.stable is True

    def test_negative_weight_rejected(self):
        r = parse_weight_line("-5.000 kg", timestamp=FIXED_TS)
        assert not r.ok
        assert r.error == "negative_weight"

    def test_zero_weight_is_a_valid_reading(self):
        r = parse_weight_line("0.000 kg", timestamp=FIXED_TS)
        assert r.ok
        assert r.weight_kg == Decimal("0.000")

    def test_empty_line_rejected(self):
        r = parse_weight_line("", timestamp=FIXED_TS)
        assert not r.ok
        assert r.error == "empty_line"

    def test_whitespace_only_rejected(self):
        r = parse_weight_line("   ", timestamp=FIXED_TS)
        assert not r.ok
        assert r.error == "empty_line"

    def test_no_numeric_rejected(self):
        r = parse_weight_line("hello world", timestamp=FIXED_TS)
        assert not r.ok
        assert r.error == "no_numeric_value"

    def test_nan_rejected(self):
        r = parse_weight_line("NaN kg", timestamp=FIXED_TS)
        assert not r.ok
        assert r.error == "nan_or_infinity"

    def test_infinity_rejected(self):
        r = parse_weight_line("INF kg", timestamp=FIXED_TS)
        assert not r.ok
        assert r.error == "nan_or_infinity"

    def test_too_many_decimals_rejected(self):
        r = parse_weight_line("1.2345 kg", timestamp=FIXED_TS)
        assert not r.ok
        assert r.error == "too_many_decimals"

    def test_unknown_unit_not_recognized(self):
        r = parse_weight_line("5.000 xy", timestamp=FIXED_TS)
        assert r.ok
        assert r.weight_kg == Decimal("5.000")
        assert r.unit == "kg"

    def test_weight_below_minimum(self):
        r = parse_weight_line("0.0005 kg", timestamp=FIXED_TS, min_weight_kg="0.001")
        assert not r.ok
        assert r.error == "too_many_decimals"

    def test_weight_above_maximum(self):
        r = parse_weight_line("1000.000 kg", timestamp=FIXED_TS, max_weight_kg="999.999")
        assert not r.ok
        assert r.error == "weight_above_maximum"

    def test_control_chars_stripped(self):
        r = parse_weight_line("\x00\x03ST 5.000 kg\x04\x00", timestamp=FIXED_TS)
        assert r.ok
        assert r.weight_kg == Decimal("5.000")
        assert r.stable is True

    def test_source_port_recorded(self):
        r = parse_weight_line("5.000 kg", source_port="COM7", timestamp=FIXED_TS)
        assert r.source_port == "COM7"

    def test_timestamp_recorded(self):
        r = parse_weight_line("5.000 kg", timestamp=FIXED_TS)
        assert r.received_at == FIXED_TS

    def test_raw_line_preserved(self):
        r = parse_weight_line("ST 5.000 kg", timestamp=FIXED_TS)
        assert r.raw_line == "ST 5.000 kg"

    def test_weight_quantized_to_three_decimals(self):
        r = parse_weight_line("5.1 kg", timestamp=FIXED_TS)
        assert r.ok
        assert r.weight_kg == Decimal("5.100")

    def test_bytes_input(self):
        r = parse_weight_line(b"ST 5.000 kg\r\n", timestamp=FIXED_TS)
        assert r.ok
        assert r.weight_kg == Decimal("5.000")

    def test_readline_trailing_newline(self):
        r = parse_weight_line("5.000 kg\r\n", timestamp=FIXED_TS)
        assert r.ok
        assert r.weight_kg == Decimal("5.000")
        assert r.raw_line == "5.000 kg"


class TestWeightReadingDTO:
    def test_to_dict_ok(self):
        r = parse_weight_line("5.000 kg", source_port="COM7", timestamp=FIXED_TS)
        d = r.to_dict()
        assert d["weight_kg"] == "5.000"
        assert d["stable"] is False
        assert d["unit"] == "kg"
        assert d["source_port"] == "COM7"
        assert d["error"] is None

    def test_to_dict_error(self):
        r = parse_weight_line("", timestamp=FIXED_TS)
        d = r.to_dict()
        assert d["error"] == "empty_line"
        assert d["weight_kg"] == "0"

    def test_ok_property(self):
        r_ok = parse_weight_line("5.000 kg", timestamp=FIXED_TS)
        r_err = parse_weight_line("", timestamp=FIXED_TS)
        assert r_ok.ok is True
        assert r_err.ok is False


class TestSanitizeForDisplay:
    def test_clean_line(self):
        assert sanitize_for_display("ST 5.000 kg") == "ST 5.000 kg"

    def test_control_chars_replaced(self):
        result = sanitize_for_display("A\x00B\x03C")
        assert "\x00" not in result
        assert "." in result

    def test_empty_string(self):
        assert sanitize_for_display("") == ""

    def test_none_input(self):
        assert sanitize_for_display(None) == ""

    def test_long_line_truncated(self):
        long = "x" * 300
        result = sanitize_for_display(long, max_length=200)
        assert len(result) == 203
        assert result.endswith("...")

    def test_angle_brackets_escaped(self):
        result = sanitize_for_display("<script>")
        assert "<" not in result
        assert ">" not in result
