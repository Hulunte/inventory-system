"""Tests for ticket_renderer.py ESC/POS pure module."""
import re

from app.services.ticket_renderer import (
    _center,
    _encode,
    _left,
    _right,
    _sanitize,
    _separator,
    _truncate,
    render_test_ticket,
    render_ticket,
)


class TestSanitize:
    def test_removes_esc(self):
        assert _sanitize("Hello\x1bWorld") == "HelloWorld"

    def test_removes_gs(self):
        assert _sanitize("Hello\x1dWorld") == "HelloWorld"

    def test_removes_nul(self):
        assert _sanitize("Hello\x00World") == "HelloWorld"

    def test_removes_cr(self):
        assert _sanitize("Hello\rWorld") == "HelloWorld"

    def test_replaces_newline_with_space(self):
        assert _sanitize("Hello\nWorld") == "Hello World"

    def test_removes_control_chars(self):
        result = _sanitize("A\x01B\x02C\x03D\x04E\x05F\x06G")
        assert result == "ABCDEFG"

    def test_preserves_normal_text(self):
        assert _sanitize("Naranja $12.50/kg") == "Naranja $12.50/kg"

    def test_empty_string(self):
        assert _sanitize("") == ""

    def test_non_string(self):
        assert _sanitize(123) == "123"

    def test_accented_characters(self):
        assert _sanitize("Trabajador 042 - Jose") == "Trabajador 042 - Jose"


class TestTruncate:
    def test_short_text_unchanged(self):
        assert _truncate("Hello", 10) == "Hello"

    def test_exact_length_unchanged(self):
        assert _truncate("Hello", 5) == "Hello"

    def test_long_text_truncated_with_tilde(self):
        result = _truncate("Hello World", 8)
        assert len(result) == 8
        assert result.endswith("~")

    def test_very_long_text(self):
        result = _truncate("A" * 100, 10)
        assert len(result) == 10
        assert result.endswith("~")


class TestCenter:
    def test_centered(self):
        result = _center("Hi", 10)
        assert len(result) == 10
        assert "Hi" in result

    def test_centered_exact(self):
        assert _center("Hello", 5) == "Hello"


class TestLeft:
    def test_left_aligned(self):
        result = _left("Hi", 10)
        assert result.startswith("Hi")
        assert len(result) <= 10


class TestRight:
    def test_right_aligned(self):
        result = _right("Hi", 10)
        assert result.endswith("Hi")
        assert len(result) == 10


class TestSeparator:
    def test_default_separator(self):
        result = _separator(10)
        assert result == "----------"
        assert len(result) == 10

    def test_custom_char(self):
        result = _separator(5, "=")
        assert result == "====="


class TestEncode:
    def test_encode_cp850(self):
        result = _encode("Hello", "cp850")
        assert isinstance(result, bytes)
        assert b"Hello" in result

    def test_encode_ascii_fallback(self):
        result = _encode("Hello", "nonexistent_encoding")
        assert isinstance(result, bytes)


class TestRenderTicket:
    def _sample_lines(self):
        return [
            {"product_name": "Naranja", "rate_per_kg": 12.50, "weight_kg": 50.000, "amount_mxn": 625.00},
            {"product_name": "Limon", "rate_per_kg": 15.00, "weight_kg": 20.000, "amount_mxn": 300.00},
        ]

    def test_returns_bytes(self):
        result = render_ticket(
            business_name="Test Business",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 042",
            worker_name="Juan Perez",
            worker_barcode="TRB000042",
            worker_assignment_id=1,
            product_lines=self._sample_lines(),
            total_weight_kg=70.000,
            total_amount_mxn=925.00,
            print_time_str="2026-06-15 14:30:00",
        )
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_contains_init_command(self):
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name="A",
            worker_barcode="TRB000001",
            worker_assignment_id=1,
            product_lines=[],
            total_weight_kg=0,
            total_amount_mxn=0,
            print_time_str="2026-06-15 10:00:00",
        )
        assert b"\x1b\x40" in result

    def test_contains_center_alignment(self):
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name="A",
            worker_barcode="TRB000001",
            worker_assignment_id=1,
            product_lines=[],
            total_weight_kg=0,
            total_amount_mxn=0,
            print_time_str="2026-06-15 10:00:00",
        )
        assert b"\x1b\x61\x01" in result

    def test_contains_date(self):
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name="A",
            worker_barcode="TRB000001",
            worker_assignment_id=1,
            product_lines=[],
            total_weight_kg=0,
            total_amount_mxn=0,
            print_time_str="2026-06-15 10:00:00",
        )
        assert b"2026-06-15" in result

    def test_contains_slot_label(self):
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 042",
            worker_name="Juan",
            worker_barcode="TRB000042",
            worker_assignment_id=1,
            product_lines=[],
            total_weight_kg=0,
            total_amount_mxn=0,
            print_time_str="2026-06-15 10:00:00",
        )
        encoded = result.decode("cp850", errors="replace")
        assert "Trabajador 042" in encoded

    def test_contains_worker_name(self):
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name="Maria Lopez",
            worker_barcode="TRB000001",
            worker_assignment_id=1,
            product_lines=[],
            total_weight_kg=0,
            total_amount_mxn=0,
            print_time_str="2026-06-15 10:00:00",
        )
        encoded = result.decode("cp850", errors="replace")
        assert "Maria Lopez" in encoded

    def test_contains_barcode(self):
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name="A",
            worker_barcode="TRB000042",
            worker_assignment_id=1,
            product_lines=[],
            total_weight_kg=0,
            total_amount_mxn=0,
            print_time_str="2026-06-15 10:00:00",
        )
        encoded = result.decode("cp850", errors="replace")
        assert "TRB000042" in encoded

    def test_contains_assignment_id(self):
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name="A",
            worker_barcode="TRB000001",
            worker_assignment_id=42,
            product_lines=[],
            total_weight_kg=0,
            total_amount_mxn=0,
            print_time_str="2026-06-15 10:00:00",
        )
        encoded = result.decode("cp850", errors="replace")
        assert "42" in encoded

    def test_contains_product_names(self):
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name="A",
            worker_barcode="TRB000001",
            worker_assignment_id=1,
            product_lines=self._sample_lines(),
            total_weight_kg=70.000,
            total_amount_mxn=925.00,
            print_time_str="2026-06-15 10:00:00",
        )
        encoded = result.decode("cp850", errors="replace")
        assert "Naranja" in encoded
        assert "Limon" in encoded

    def test_contains_totals(self):
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name="A",
            worker_barcode="TRB000001",
            worker_assignment_id=1,
            product_lines=self._sample_lines(),
            total_weight_kg=70.000,
            total_amount_mxn=925.00,
            print_time_str="2026-06-15 10:00:00",
        )
        encoded = result.decode("cp850", errors="replace")
        assert "70.000" in encoded
        assert "925.00" in encoded

    def test_contains_print_time(self):
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name="A",
            worker_barcode="TRB000001",
            worker_assignment_id=1,
            product_lines=[],
            total_weight_kg=0,
            total_amount_mxn=0,
            print_time_str="2026-06-15 14:30:00",
        )
        encoded = result.decode("cp850", errors="replace")
        assert "14:30:00" in encoded

    def test_auto_cut_enabled(self):
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name="A",
            worker_barcode="TRB000001",
            worker_assignment_id=1,
            product_lines=[],
            total_weight_kg=0,
            total_amount_mxn=0,
            print_time_str="2026-06-15 10:00:00",
            auto_cut=True,
        )
        assert result.endswith(b"\x1d\x56\x01")

    def test_auto_cut_disabled(self):
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name="A",
            worker_barcode="TRB000001",
            worker_assignment_id=1,
            product_lines=[],
            total_weight_kg=0,
            total_amount_mxn=0,
            print_time_str="2026-06-15 10:00:00",
            auto_cut=False,
        )
        assert not result.endswith(b"\x1d\x56\x01")

    def test_incomplete_amounts_warning(self):
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name="A",
            worker_barcode="TRB000001",
            worker_assignment_id=1,
            product_lines=[],
            total_weight_kg=0,
            total_amount_mxn=0,
            print_time_str="2026-06-15 10:00:00",
            has_incomplete_amounts=True,
        )
        encoded = result.decode("cp850", errors="replace")
        assert "historico" in encoded.lower() or "incompleto" in encoded.lower()
        assert "PAGO CALCULABLE" in encoded

    def test_no_incomplete_uses_pago_total(self):
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name="A",
            worker_barcode="TRB000001",
            worker_assignment_id=1,
            product_lines=self._sample_lines(),
            total_weight_kg=70.000,
            total_amount_mxn=925.00,
            print_time_str="2026-06-15 10:00:00",
            has_incomplete_amounts=False,
        )
        encoded = result.decode("cp850", errors="replace")
        assert "PAGO TOTAL:" in encoded
        assert "PAGO CALCULABLE" not in encoded

    def test_footer_text(self):
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name="A",
            worker_barcode="TRB000001",
            worker_assignment_id=1,
            product_lines=[],
            total_weight_kg=0,
            total_amount_mxn=0,
            print_time_str="2026-06-15 10:00:00",
            footer_text="Gracias por su compra",
        )
        encoded = result.decode("cp850", errors="replace")
        assert "Gracias por su compra" in encoded

    def test_control_chars_in_names_stripped(self):
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name="Juan\x1bPerez",
            worker_barcode="TRB000001",
            worker_assignment_id=1,
            product_lines=[],
            total_weight_kg=0,
            total_amount_mxn=0,
            print_time_str="2026-06-15 10:00:00",
        )
        raw = result
        assert b"\x1bPerez" not in raw

    def test_long_name_truncated(self):
        long_name = "A" * 100
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name=long_name,
            worker_barcode="TRB000001",
            worker_assignment_id=1,
            product_lines=[],
            total_weight_kg=0,
            total_amount_mxn=0,
            print_time_str="2026-06-15 10:00:00",
            cpl=48,
        )
        text = result.decode("cp850", errors="replace")
        for line in text.split("\n"):
            stripped = line.strip("\x1b\x40\x61\x00\x01")
            if stripped:
                assert len(stripped) <= 48

    def test_deterministic_output(self):
        kwargs = dict(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name="Juan",
            worker_barcode="TRB000001",
            worker_assignment_id=1,
            product_lines=self._sample_lines(),
            total_weight_kg=70.000,
            total_amount_mxn=925.00,
            print_time_str="2026-06-15 10:00:00",
        )
        r1 = render_ticket(**kwargs)
        r2 = render_ticket(**kwargs)
        assert r1 == r2

    def test_cpl_48_no_line_exceeds(self):
        result = render_ticket(
            business_name="Test Business Name Here",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 042",
            worker_name="Juan Perez Garcia",
            worker_barcode="TRB000042",
            worker_assignment_id=1,
            product_lines=self._sample_lines(),
            total_weight_kg=70.000,
            total_amount_mxn=925.00,
            print_time_str="2026-06-15 10:00:00",
            cpl=48,
        )
        text = result.decode("cp850", errors="replace")
        for line in text.split("\n"):
            stripped = line.strip("\x1b\x40\x61\x00\x01")
            if stripped:
                assert len(stripped) <= 48

    def test_none_amount_shows_no_disponible(self):
        lines = [
            {"product_name": "Naranja", "rate_per_kg": 12.50, "weight_kg": 50.000, "amount_mxn": None},
        ]
        result = render_ticket(
            business_name="Test",
            operational_date_str="2026-06-15",
            slot_label="Trabajador 001",
            worker_name="A",
            worker_barcode="TRB000001",
            worker_assignment_id=1,
            product_lines=lines,
            total_weight_kg=50.000,
            total_amount_mxn=0,
            print_time_str="2026-06-15 10:00:00",
            has_incomplete_amounts=True,
        )
        encoded = result.decode("cp850", errors="replace")
        assert "N/D" in encoded


class TestRenderTestTicket:
    def test_returns_bytes(self):
        result = render_test_ticket("Test Business", "2026-06-15 10:00:00")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_contains_init(self):
        result = render_test_ticket("Test", "2026-06-15 10:00:00")
        assert b"\x1b\x40" in result

    def test_contains_prueba(self):
        result = render_test_ticket("Test Business", "2026-06-15 10:00:00")
        encoded = result.decode("cp850", errors="replace")
        assert "Prueba de impresion" in encoded

    def test_contains_business_name(self):
        result = render_test_ticket("Mi Negocio", "2026-06-15 10:00:00")
        encoded = result.decode("cp850", errors="replace")
        assert "Mi Negocio" in encoded

    def test_auto_cut(self):
        result = render_test_ticket("Test", "2026-06-15 10:00:00", auto_cut=True)
        assert result.endswith(b"\x1d\x56\x01")

    def test_no_auto_cut(self):
        result = render_test_ticket("Test", "2026-06-15 10:00:00", auto_cut=False)
        assert not result.endswith(b"\x1d\x56\x01")

    def test_no_flask_imports(self):
        import app.services.ticket_renderer as mod
        source_lines = open(mod.__file__).read()
        assert "from flask" not in source_lines
        assert "import flask" not in source_lines

    def test_no_db_imports(self):
        import app.services.ticket_renderer as mod
        source_lines = open(mod.__file__).read()
        assert "SQLAlchemy" not in source_lines
        assert "from app.extensions" not in source_lines

    def test_no_win32print_imports(self):
        import app.services.ticket_renderer as mod
        source_lines = open(mod.__file__).read()
        lines = [l for l in source_lines.split("\n") if not l.strip().startswith('"""') and not l.strip().startswith("'''")]
        source_no_docstrings = "\n".join(lines)
        assert "win32print" not in source_no_docstrings
        assert "import win32" not in source_no_docstrings
