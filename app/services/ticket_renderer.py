"""Pure ESC/POS ticket renderer. No Flask, no DB, no win32print imports."""

import re
from datetime import datetime
from decimal import Decimal

_CONTROL_RE = re.compile(
    r"[\x00-\x1f\x7f]"
)


def _sanitize(text):
    """Remove ESC/POS control characters from user-provided text."""
    if not isinstance(text, str):
        text = str(text)
    text = text.replace("\n", " ")
    text = text.replace("\r", "")
    text = _CONTROL_RE.sub("", text)
    return text


def _truncate(text, max_len):
    if len(text) > max_len:
        return text[: max_len - 1] + "~"
    return text


def _center(text, width):
    return text.center(width)


def _left(text, width):
    return _truncate(text, width)


def _right(text, width):
    truncated = _truncate(text, width)
    return truncated.rjust(width)


def _separator(width, char="-"):
    return char * width


def _encode(text, encoding="cp850"):
    safe = _sanitize(text)
    try:
        return safe.encode(encoding, errors="replace")
    except (LookupError, UnicodeEncodeError):
        return safe.encode("ascii", errors="replace")


def render_ticket(
    business_name,
    operational_date_str,
    slot_label,
    worker_name,
    worker_barcode,
    worker_assignment_id,
    product_lines,
    total_weight_kg,
    total_amount_mxn,
    print_time_str,
    has_incomplete_amounts=False,
    footer_text="Conserve este comprobante",
    cpl=48,
    encoding="cp850",
    auto_cut=True,
):
    """Render a single worker ticket to ESC/POS bytes.

    Args:
        business_name: Name of the business (centered header).
        operational_date_str: Date string like "2026-01-15".
        slot_label: e.g. "Trabajador 042".
        worker_name: Historical worker name.
        worker_barcode: Historical barcode.
        worker_assignment_id: Assignment ID.
        product_lines: List of dicts with product_name, rate_per_kg, weight_kg, amount_mxn.
        total_weight_kg: Decimal total weight.
        total_amount_mxn: Decimal total amount.
        print_time_str: Formatted print timestamp.
        has_incomplete_amounts: Whether to show incomplete warning.
        footer_text: Final text.
        cpl: Characters per line.
        encoding: Character encoding.
        auto_cut: Whether to send partial cut command.

    Returns:
        bytes: ESC/POS command sequence.
    """
    buf = bytearray()

    buf.extend(b"\x1b\x40")
    buf.extend(b"\x1b\x61\x01")

    name_lines = _sanitize(business_name)
    for line in name_lines.split("\n"):
        buf.extend(_encode(_center(line.strip(), cpl), encoding))
        buf.extend(b"\n")

    buf.extend(_encode(_center(_separator(cpl, "="), cpl), encoding))
    buf.extend(b"\n")

    buf.extend(_encode(_center("Comprobante de jornada", cpl), encoding))
    buf.extend(b"\n")

    buf.extend(_encode(_center(_separator(cpl, "-"), cpl), encoding))
    buf.extend(b"\n")

    buf.extend(b"\x1b\x61\x00")

    buf.extend(_encode(_left(f"Fecha: {_sanitize(operational_date_str)}", cpl), encoding))
    buf.extend(b"\n")

    buf.extend(_encode(_left(f"{_sanitize(slot_label)}", cpl), encoding))
    buf.extend(b"\n")

    buf.extend(_encode(_left(f"Nombre: {_sanitize(worker_name)}", cpl), encoding))
    buf.extend(b"\n")

    buf.extend(_encode(_left(f"Codigo: {_sanitize(worker_barcode)}", cpl), encoding))
    buf.extend(b"\n")

    buf.extend(_encode(_left(f"Asignacion: {worker_assignment_id}", cpl), encoding))
    buf.extend(b"\n")

    buf.extend(_encode(_separator(cpl, "-"), encoding))
    buf.extend(b"\n")

    for line_data in product_lines:
        pname = _sanitize(line_data["product_name"])
        rate = Decimal(str(line_data["rate_per_kg"]))
        weight = Decimal(str(line_data["weight_kg"]))
        amount = line_data["amount_mxn"]

        name_col_width = cpl - 14
        buf.extend(_encode(_truncate(pname, name_col_width), encoding))
        buf.extend(b"\n")

        detail = f"  {weight:.3f} kg x ${rate:.2f}"
        buf.extend(_encode(_left(detail, cpl - 10), encoding))
        if amount is not None:
            amount_str = f"${Decimal(str(amount)):.2f}"
        else:
            amount_str = "N/D"
        buf.extend(_encode(_right(amount_str, 10), encoding))
        buf.extend(b"\n")

    buf.extend(_encode(_separator(cpl, "-"), encoding))
    buf.extend(b"\n")

    total_w = Decimal(str(total_weight_kg))
    total_a = Decimal(str(total_amount_mxn))

    total_line_left = "TOTAL kg:"
    total_line_right = f"{total_w:.3f}"
    left_width = cpl - len(total_line_right) - 1
    buf.extend(_encode(_left(total_line_left, left_width), encoding))
    buf.extend(b" ")
    buf.extend(_encode(total_line_right, encoding))
    buf.extend(b"\n")

    if has_incomplete_amounts:
        pay_left = "PAGO CALCULABLE:"
    else:
        pay_left = "PAGO TOTAL:"
    pay_right = f"${total_a:.2f}"
    left_width_pay = cpl - len(pay_right) - 1
    buf.extend(_encode(_left(pay_left, left_width_pay), encoding))
    buf.extend(b" ")
    buf.extend(_encode(pay_right, encoding))
    buf.extend(b"\n")

    if has_incomplete_amounts:
        buf.extend(b"\n")
        warning = "Este ticket contiene movimientos historicos sin precio y su pago puede estar incompleto."
        for i in range(0, len(warning), cpl):
            chunk = warning[i: i + cpl]
            buf.extend(_encode(_center(chunk, cpl), encoding))
            buf.extend(b"\n")

    buf.extend(_encode(_separator(cpl, "-"), encoding))
    buf.extend(b"\n")

    buf.extend(_encode(_center(_sanitize(print_time_str), cpl), encoding))
    buf.extend(b"\n")

    buf.extend(_encode(_center(_sanitize(footer_text), cpl), encoding))
    buf.extend(b"\n")

    buf.extend(b"\n")
    buf.extend(b"\n")
    buf.extend(b"\n")

    if auto_cut:
        buf.extend(b"\x1d\x56\x01")

    return bytes(buf)


def render_test_ticket(business_name, print_time_str, cpl=48, encoding="cp850", auto_cut=True):
    """Render a small test ticket for printer verification."""
    buf = bytearray()

    buf.extend(b"\x1b\x40")
    buf.extend(b"\x1b\x61\x01")

    buf.extend(_encode(_center("Prueba de impresion", cpl), encoding))
    buf.extend(b"\n")
    buf.extend(_encode(_center(_sanitize(business_name), cpl), encoding))
    buf.extend(b"\n")
    buf.extend(_encode(_center(_separator(cpl, "="), cpl), encoding))
    buf.extend(b"\n")

    buf.extend(b"\x1b\x61\x00")
    buf.extend(_encode(_center(_sanitize(print_time_str), cpl), encoding))
    buf.extend(b"\n")
    buf.extend(_encode(_center(f"Ancho: {cpl} caracteres", cpl), encoding))
    buf.extend(b"\n")

    buf.extend(b"\n")
    buf.extend(b"\n")
    buf.extend(b"\n")

    if auto_cut:
        buf.extend(b"\x1d\x56\x01")

    return bytes(buf)
