from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Optional

from flask import current_app
from sqlalchemy import func

from app.extensions import db
from app.models.harvest_entry import HarvestEntry


@dataclass
class ProductLine:
    product_name: str
    rate_per_kg: Decimal
    weight_kg: Decimal
    amount_mxn: Optional[Decimal]


@dataclass
class WorkerTicket:
    worker_assignment_id: int
    slot_number: int
    slot_label: str
    worker_name: str
    worker_barcode: str
    product_lines: list = field(default_factory=list)
    total_weight_kg: Decimal = Decimal("0.000")
    total_amount_mxn: Decimal = Decimal("0.000")
    has_incomplete_amounts: bool = False


def _get_tz():
    return current_app.config["HARVEST_TIMEZONE"]


def _date_range_to_utc(operational_date, tz=None):
    if tz is None:
        tz = _get_tz()
    start_of_day = datetime.combine(operational_date, time.min, tzinfo=tz)
    end_of_day = start_of_day + timedelta(days=1)
    return start_of_day.astimezone(timezone.utc), end_of_day.astimezone(timezone.utc)


def get_daily_tickets(operational_date, query_filter=None, tz=None):
    """Get daily ticket summaries for all workers on a given operational date.

    Returns a list of WorkerTicket objects sorted by slot_number, then assignment ID.
    Each ticket groups by (worker_assignment_id, product_name_snapshot, rate_per_kg_snapshot).
    """
    if tz is None:
        tz = _get_tz()

    start_utc, end_utc = _date_range_to_utc(operational_date, tz)

    q = (
        db.session.query(
            HarvestEntry.worker_assignment_id,
            HarvestEntry.worker_slot_number_snapshot,
            HarvestEntry.worker_name_snapshot,
            HarvestEntry.worker_barcode_snapshot,
            HarvestEntry.product_name_snapshot,
            HarvestEntry.rate_per_kg_snapshot,
            func.coalesce(func.sum(HarvestEntry.weight_kg), Decimal("0")).label("total_weight_kg"),
            func.coalesce(func.sum(HarvestEntry.amount_mxn), Decimal("0")).label("total_amount_mxn"),
        )
        .filter(
            HarvestEntry.created_at >= start_utc,
            HarvestEntry.created_at < end_utc,
            HarvestEntry.voided == False,
        )
        .group_by(
            HarvestEntry.worker_assignment_id,
            HarvestEntry.worker_slot_number_snapshot,
            HarvestEntry.worker_name_snapshot,
            HarvestEntry.worker_barcode_snapshot,
            HarvestEntry.product_name_snapshot,
            HarvestEntry.rate_per_kg_snapshot,
        )
        .order_by(
            HarvestEntry.worker_slot_number_snapshot.asc().nullslast(),
            HarvestEntry.worker_assignment_id.asc(),
        )
    )

    if query_filter:
        pattern = f"%{query_filter}%"
        q = q.filter(
            db.or_(
                HarvestEntry.worker_name_snapshot.ilike(pattern),
                HarvestEntry.worker_barcode_snapshot.ilike(pattern),
                func.cast(HarvestEntry.worker_slot_number_snapshot, db.String).ilike(pattern),
            )
        )

    rows = q.all()

    tickets_map = {}
    for r in rows:
        assignment_id = r.worker_assignment_id
        if assignment_id is None:
            continue

        if assignment_id not in tickets_map:
            slot_num = r.worker_slot_number_snapshot
            tickets_map[assignment_id] = WorkerTicket(
                worker_assignment_id=assignment_id,
                slot_number=slot_num or 0,
                slot_label=f"Trabajador {slot_num:03d}" if slot_num else "Sin cupo",
                worker_name=r.worker_name_snapshot or "Sin nombre",
                worker_barcode=r.worker_barcode_snapshot or "",
            )

        ticket = tickets_map[assignment_id]

        weight = Decimal(str(r.total_weight_kg))
        amount = Decimal(str(r.total_amount_mxn))

        if r.product_name_snapshot and r.rate_per_kg_snapshot is not None:
            line = ProductLine(
                product_name=r.product_name_snapshot,
                rate_per_kg=Decimal(str(r.rate_per_kg_snapshot)),
                weight_kg=weight,
                amount_mxn=amount,
            )
            ticket.product_lines.append(line)
            ticket.total_weight_kg += weight
            ticket.total_amount_mxn += amount
        else:
            ticket.has_incomplete_amounts = True
            line = ProductLine(
                product_name="Sin producto/precio historico",
                rate_per_kg=Decimal("0"),
                weight_kg=weight,
                amount_mxn=None,
            )
            ticket.product_lines.append(line)
            ticket.total_weight_kg += weight

    tickets = sorted(tickets_map.values(), key=lambda t: (t.slot_number, t.worker_assignment_id))

    total_day_weight = Decimal("0.000")
    total_day_amount = Decimal("0.000")
    for t in tickets:
        total_day_weight += t.total_weight_kg
        total_day_amount += t.total_amount_mxn

    return {
        "date": operational_date.isoformat(),
        "tickets": tickets,
        "total_workers": len(tickets),
        "total_day_weight_kg": total_day_weight,
        "total_day_amount_mxn": total_day_amount,
    }


def get_single_ticket(operational_date, worker_assignment_id, tz=None):
    """Get a single ticket for a specific worker assignment on a given date."""
    result = get_daily_tickets(operational_date, tz=tz)

    for ticket in result["tickets"]:
        if ticket.worker_assignment_id == worker_assignment_id:
            return ticket

    return None


def serialize_ticket(ticket):
    """Serialize a WorkerTicket to a JSON-safe dict."""
    return {
        "worker_assignment_id": ticket.worker_assignment_id,
        "slot_number": ticket.slot_number,
        "slot_label": ticket.slot_label,
        "worker_name": ticket.worker_name,
        "worker_barcode": ticket.worker_barcode,
        "product_lines": [
            {
                "product_name": line.product_name,
                "rate_per_kg": f"{line.rate_per_kg:.2f}",
                "weight_kg": f"{line.weight_kg:.3f}",
                "amount_mxn": f"{line.amount_mxn:.2f}" if line.amount_mxn is not None else None,
            }
            for line in ticket.product_lines
        ],
        "total_weight_kg": f"{ticket.total_weight_kg:.3f}",
        "total_amount_mxn": f"{ticket.total_amount_mxn:.2f}",
        "has_incomplete_amounts": ticket.has_incomplete_amounts,
    }


def serialize_daily_response(result):
    """Serialize the full daily ticket response."""
    return {
        "date": result["date"],
        "tickets": [serialize_ticket(t) for t in result["tickets"]],
        "total_workers": result["total_workers"],
        "total_day_weight_kg": f"{result['total_day_weight_kg']:.3f}",
        "total_day_amount_mxn": f"{result['total_day_amount_mxn']:.2f}",
    }
