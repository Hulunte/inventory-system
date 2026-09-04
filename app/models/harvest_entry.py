from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, ForeignKey, Index

from app.extensions import db


class HarvestEntry(db.Model):
    __tablename__ = "harvest_entries"
    __table_args__ = (
        CheckConstraint("weight_kg > 0", name="ck_harvest_entries_weight_positive"),
        CheckConstraint(
            "(NOT voided AND voided_at IS NULL AND void_reason IS NULL) OR "
            "(voided AND voided_at IS NOT NULL AND void_reason IS NOT NULL AND LENGTH(TRIM(void_reason)) > 0)",
            name="ck_harvest_entries_voided_consistency",
        ),
        CheckConstraint(
            "rate_per_kg_snapshot IS NULL OR rate_per_kg_snapshot >= 0",
            name="ck_harvest_entries_rate_snapshot_non_negative",
        ),
        CheckConstraint(
            "amount_mxn IS NULL OR amount_mxn >= 0",
            name="ck_harvest_entries_amount_non_negative",
        ),
        CheckConstraint(
            "(product_id IS NULL AND product_name_snapshot IS NULL "
            "AND rate_per_kg_snapshot IS NULL AND amount_mxn IS NULL) OR "
            "(product_id IS NOT NULL AND product_name_snapshot IS NOT NULL "
            "AND rate_per_kg_snapshot IS NOT NULL AND amount_mxn IS NOT NULL)",
            name="ck_harvest_entries_product_snapshot_consistency",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    worker_id = db.Column(
        db.Integer, db.ForeignKey("workers.id"), nullable=False, index=True
    )

    weight_kg = db.Column(db.Numeric(10, 3), nullable=False)

    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id"), nullable=True, index=True
    )
    product_name_snapshot = db.Column(db.String(100), nullable=True)
    rate_per_kg_snapshot = db.Column(db.Numeric(8, 2), nullable=True)
    amount_mxn = db.Column(db.Numeric(12, 2), nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    voided = db.Column(db.Boolean, nullable=False, default=False, index=True)
    voided_at = db.Column(db.DateTime(timezone=True), nullable=True)
    void_reason = db.Column(db.Text, nullable=True)

    worker = db.relationship("Worker", backref="harvest_entries")
    product = db.relationship("Product")

    def __repr__(self):
        return f"<HarvestEntry {self.weight_kg}kg>"
