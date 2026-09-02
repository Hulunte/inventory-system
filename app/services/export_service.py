from decimal import Decimal
from io import BytesIO

from flask import current_app
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter

from app.extensions import db
from app.models.harvest_entry import HarvestEntry
from app.models.worker import Worker
from app.services.report_service import date_range_to_utc

_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def _safe_text(value):
    """Prepend an apostrophe to strings that Excel could interpret as formulas."""
    if not isinstance(value, str):
        return value
    if value and value[0] in _DANGEROUS_PREFIXES:
        return "'" + value
    return value


def _to_local_naive(dt_utc, tz):
    """Convert a UTC datetime to a timezone-aware local datetime, then strip tzinfo.

    openpyxl does not support timezone-aware datetimes.
    """
    if dt_utc is None:
        return None
    return dt_utc.astimezone(tz).replace(tzinfo=None)


def _write_header_row(ws, headers):
    header_font = Font(bold=True)
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")


def _auto_width(ws):
    for col_cells in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col_cells[0].column)
        for cell in col_cells:
            val = str(cell.value) if cell.value is not None else ""
            if len(val) > max_len:
                max_len = len(val)
        ws.column_dimensions[col_letter].width = min(max(max_len + 8, 10), 50)


def generate_harvest_export(start_date, end_date, query_filter=None, tz=None):
    """Generate an Excel workbook with Movimientos and Resumen sheets.

    Returns the workbook content as bytes.
    """
    if tz is None:
        tz = current_app.config["HARVEST_TIMEZONE"]

    start_utc, end_utc = date_range_to_utc(start_date, end_date, tz)

    q = (
        db.session.query(
            HarvestEntry.id,
            HarvestEntry.created_at,
            HarvestEntry.weight_kg,
            HarvestEntry.voided,
            HarvestEntry.voided_at,
            HarvestEntry.void_reason,
            Worker.name.label("worker_name"),
            Worker.barcode.label("worker_barcode"),
        )
        .join(Worker, HarvestEntry.worker_id == Worker.id)
        .filter(
            HarvestEntry.created_at >= start_utc,
            HarvestEntry.created_at < end_utc,
        )
        .order_by(HarvestEntry.created_at.asc(), HarvestEntry.id.asc())
    )

    if query_filter:
        pattern = f"%{query_filter}%"
        q = q.filter(
            db.or_(
                Worker.name.ilike(pattern),
                Worker.barcode.ilike(pattern),
            )
        )

    entries = q.all()

    wb = Workbook()

    # --- Hoja Movimientos ---
    ws_mov = wb.active
    ws_mov.title = "Movimientos"

    mov_headers = [
        "ID", "Fecha", "Hora", "Trabajador", "Código",
        "Peso (kg)", "Estado", "Fecha y hora de anulación", "Motivo de anulación",
    ]
    _write_header_row(ws_mov, mov_headers)

    for row_idx, entry in enumerate(entries, 2):
        local_created = _to_local_naive(entry.created_at, tz)
        local_voided = _to_local_naive(entry.voided_at, tz)

        ws_mov.cell(row=row_idx, column=1, value=entry.id)

        date_cell = ws_mov.cell(row=row_idx, column=2, value=local_created.date() if local_created else None)
        date_cell.number_format = "YYYY-MM-DD"

        time_cell = ws_mov.cell(row=row_idx, column=3, value=local_created.time() if local_created else None)
        time_cell.number_format = "HH:MM:SS"

        ws_mov.cell(row=row_idx, column=4, value=_safe_text(entry.worker_name))
        ws_mov.cell(row=row_idx, column=5, value=_safe_text(entry.worker_barcode))

        weight_cell = ws_mov.cell(row=row_idx, column=6, value=Decimal(str(entry.weight_kg)))
        weight_cell.number_format = "0.000"

        ws_mov.cell(row=row_idx, column=7, value="Anulado" if entry.voided else "Vigente")

        if local_voided:
            voided_cell = ws_mov.cell(row=row_idx, column=8, value=local_voided)
            voided_cell.number_format = "YYYY-MM-DD HH:MM:SS"
        else:
            ws_mov.cell(row=row_idx, column=8, value=None)

        ws_mov.cell(row=row_idx, column=9, value=_safe_text(entry.void_reason) if entry.void_reason else None)

    ws_mov.freeze_panes = "A2"
    ws_mov.auto_filter.ref = f"A1:I{len(entries) + 1}"
    _auto_width(ws_mov)

    # --- Hoja Resumen ---
    ws_res = wb.create_sheet(title="Resumen")

    res_headers = [
        "Trabajador", "Código", "Movimientos vigentes",
        "Peso vigente (kg)", "Movimientos anulados", "Peso anulado (kg)",
    ]
    _write_header_row(ws_res, res_headers)

    worker_summary = {}
    for entry in entries:
        key = (entry.worker_name, entry.worker_barcode)
        if key not in worker_summary:
            worker_summary[key] = {
                "vigentes_count": 0,
                "vigentes_weight": Decimal("0.000"),
                "anulados_count": 0,
                "anulados_weight": Decimal("0.000"),
            }
        ws = worker_summary[key]
        w = Decimal(str(entry.weight_kg))
        if entry.voided:
            ws["anulados_count"] += 1
            ws["anulados_weight"] += w
        else:
            ws["vigentes_count"] += 1
            ws["vigentes_weight"] += w

    total_vig_count = 0
    total_vig_weight = Decimal("0.000")
    total_anul_count = 0
    total_anul_weight = Decimal("0.000")

    worker_data_rows = 0
    row_idx = 2
    for (name, barcode), data in sorted(worker_summary.items()):
        ws_res.cell(row=row_idx, column=1, value=_safe_text(name))
        ws_res.cell(row=row_idx, column=2, value=_safe_text(barcode))
        ws_res.cell(row=row_idx, column=3, value=data["vigentes_count"])

        vig_cell = ws_res.cell(row=row_idx, column=4, value=data["vigentes_weight"])
        vig_cell.number_format = "0.000"

        ws_res.cell(row=row_idx, column=5, value=data["anulados_count"])

        anul_cell = ws_res.cell(row=row_idx, column=6, value=data["anulados_weight"])
        anul_cell.number_format = "0.000"

        total_vig_count += data["vigentes_count"]
        total_vig_weight += data["vigentes_weight"]
        total_anul_count += data["anulados_count"]
        total_anul_weight += data["anulados_weight"]

        worker_data_rows += 1
        row_idx += 1

    # Fila de totales
    total_font = Font(bold=True)
    ws_res.cell(row=row_idx, column=1, value="TOTALES").font = total_font
    ws_res.cell(row=row_idx, column=2).font = total_font
    ws_res.cell(row=row_idx, column=3, value=total_vig_count).font = total_font

    tv_cell = ws_res.cell(row=row_idx, column=4, value=total_vig_weight)
    tv_cell.number_format = "0.000"
    tv_cell.font = total_font

    ws_res.cell(row=row_idx, column=5, value=total_anul_count).font = total_font

    ta_cell = ws_res.cell(row=row_idx, column=6, value=total_anul_weight)
    ta_cell.number_format = "0.000"
    ta_cell.font = total_font

    # Autofilter covers header + worker rows only, excluding TOTALES
    res_last_row = 1 + worker_data_rows if worker_data_rows else 1
    ws_res.freeze_panes = "A2"
    ws_res.auto_filter.ref = f"A1:F{res_last_row}"
    _auto_width(ws_res)

    # --- Guardar en memoria ---
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
