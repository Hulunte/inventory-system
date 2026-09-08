from sqlalchemy import String, cast

from app.extensions import db
from app.models.harvest_entry import HarvestEntry


def get_voided_entries(query_filter=None):
    query = HarvestEntry.query.filter(HarvestEntry.voided.is_(True))

    if query_filter:
        pattern = f"%{query_filter}%"
        query = query.filter(
            db.or_(
                HarvestEntry.worker_name_snapshot.ilike(pattern),
                HarvestEntry.worker_barcode_snapshot.ilike(pattern),
                HarvestEntry.product_name_snapshot.ilike(pattern),
                cast(HarvestEntry.worker_slot_number_snapshot, String).ilike(pattern),
            )
        )

    return query.order_by(
        HarvestEntry.voided_at.desc(), HarvestEntry.id.desc()
    ).all()
