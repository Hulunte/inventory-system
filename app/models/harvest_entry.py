from datetime import datetime, timezone

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import synonym

from app.extensions import db


class HarvestEntry(db.Model):
    __tablename__ = "harvest_entries"
    __table_args__ = (
        CheckConstraint("weight_kg > 0", name="ck_harvest_entries_weight_positive"),
        CheckConstraint(
            "(NOT voided AND voided_at IS NULL AND void_reason IS NULL) OR "
            "(voided AND voided_at IS NOT NULL AND void_reason IS NOT NULL "
            "AND LENGTH(TRIM(void_reason)) > 0)",
            name="ck_harvest_entries_voided_consistency",
        ),
        CheckConstraint(
            "rate_per_kg_snapshot IS NULL OR rate_per_kg_snapshot >= 0",
            name="ck_harvest_entries_rate_snapshot_non_negative",
        ),
        CheckConstraint(
            "rate_per_sack_snapshot IS NULL OR rate_per_sack_snapshot >= 0",
            name="ck_harvest_entries_sack_rate_snapshot_non_negative",
        ),
        CheckConstraint(
            "amount_mxn IS NULL OR amount_mxn >= 0",
            name="ck_harvest_entries_amount_non_negative",
        ),
        CheckConstraint(
            "(product_id IS NULL AND product_name_snapshot IS NULL "
            "AND rate_per_kg_snapshot IS NULL AND rate_per_sack_snapshot IS NULL "
            "AND amount_mxn IS NULL) OR "
            "(product_id IS NOT NULL AND product_name_snapshot IS NOT NULL "
            "AND amount_mxn IS NOT NULL AND ("
            "(registration_type = 'scale' AND rate_per_kg_snapshot IS NOT NULL "
            "AND rate_per_sack_snapshot IS NULL) OR "
            "(registration_type = 'sacks' AND "
            "(rate_per_sack_snapshot IS NOT NULL OR rate_per_kg_snapshot IS NOT NULL))))",
            name="ck_harvest_entries_product_snapshot_consistency",
        ),
        CheckConstraint(
            "(worker_assignment_id IS NULL AND worker_slot_number_snapshot IS NULL "
            "AND worker_barcode_snapshot IS NULL AND worker_name_snapshot IS NULL) OR "
            "(worker_assignment_id IS NOT NULL AND worker_slot_number_snapshot IS NOT NULL "
            "AND worker_barcode_snapshot IS NOT NULL AND worker_name_snapshot IS NOT NULL)",
            name="ck_harvest_entries_worker_snapshot_consistency",
        ),
        CheckConstraint(
            "(registration_type = 'scale' AND sack_count IS NULL AND average_sack_weight_kg_snapshot IS NULL) OR "
            "(registration_type = 'sacks' AND sack_count > 0 AND average_sack_weight_kg_snapshot > 0)",
            name="ck_harvest_entries_registration_type_consistency",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    worker_id = db.Column(
        db.Integer, db.ForeignKey("workers.id"), nullable=False, index=True
    )

    weight_kg = db.Column(db.Numeric(10, 3), nullable=False)

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    product_name_snapshot = db.Column(db.String(100), nullable=True)
    rate_per_kg_snapshot = db.Column(db.Numeric(8, 2), nullable=True)
    amount_mxn = db.Column(db.Numeric(12, 2), nullable=True)
    registration_type = db.Column(db.String(10), nullable=False, default="scale")
    # Public domain name for the persisted registration_type column. Keeping a
    # synonym avoids duplicating schema or rewriting historical rows.
    measurement_mode = synonym("registration_type")
    sack_count = db.Column(db.Integer, nullable=True)
    average_sack_weight_kg_snapshot = db.Column(db.Numeric(10, 3), nullable=True)
    rate_per_sack_snapshot = db.Column(db.Numeric(8, 2), nullable=True)
    price_per_sack_snapshot = synonym("rate_per_sack_snapshot")

    worker_assignment_id = db.Column(
        db.Integer,
        db.ForeignKey("worker_assignments.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    worker_slot_number_snapshot = db.Column(db.Integer, nullable=True)
    worker_barcode_snapshot = db.Column(db.String(100), nullable=True)
    worker_name_snapshot = db.Column(db.String(150), nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    voided = db.Column(db.Boolean, nullable=False, default=False, index=True)
    voided_at = db.Column(db.DateTime(timezone=True), nullable=True)
    void_reason = db.Column(db.Text, nullable=True)

    worker = db.relationship("Worker", backref="harvest_entries")
    product = db.relationship("Product")
    assignment = db.relationship("WorkerAssignment")

    def __repr__(self):
        return f"<HarvestEntry {self.weight_kg}kg>"
