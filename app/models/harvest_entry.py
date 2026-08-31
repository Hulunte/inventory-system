from datetime import datetime, timezone

from sqlalchemy import CheckConstraint

from app.extensions import db


class HarvestEntry(db.Model):
    __tablename__ = "harvest_entries"
    __table_args__ = (
        CheckConstraint("weight_kg > 0", name="ck_harvest_entries_weight_positive"),
    )

    id = db.Column(db.Integer, primary_key=True)

    worker_id = db.Column(
        db.Integer, db.ForeignKey("workers.id"), nullable=False, index=True
    )

    weight_kg = db.Column(db.Numeric(10, 3), nullable=False)

    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    worker = db.relationship("Worker", backref="harvest_entries")

    def __repr__(self):
        return f"<HarvestEntry {self.weight_kg}kg>"
