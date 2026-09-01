from datetime import datetime, timezone

from sqlalchemy import CheckConstraint

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
    )

    id = db.Column(db.Integer, primary_key=True)

    worker_id = db.Column(
        db.Integer, db.ForeignKey("workers.id"), nullable=False, index=True
    )

    weight_kg = db.Column(db.Numeric(10, 3), nullable=False)

    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    voided = db.Column(db.Boolean, nullable=False, default=False, index=True)
    voided_at = db.Column(db.DateTime(timezone=True), nullable=True)
    void_reason = db.Column(db.Text, nullable=True)

    worker = db.relationship("Worker", backref="harvest_entries")

    def __repr__(self):
        return f"<HarvestEntry {self.weight_kg}kg>"
