from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Index, func

from app.extensions import db


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    rate_per_kg = db.Column(db.Numeric(8, 2), nullable=False)
    average_sack_weight_kg = db.Column(db.Numeric(10, 3), nullable=True)
    rate_per_sack = db.Column(db.Numeric(8, 2), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ux_products_name_lower", func.lower(name), unique=True),
        CheckConstraint("rate_per_kg >= 0", name="ck_products_rate_non_negative"),
        CheckConstraint(
            "average_sack_weight_kg IS NULL OR average_sack_weight_kg > 0",
            name="ck_products_average_sack_weight_positive",
        ),
        CheckConstraint("rate_per_sack IS NULL OR rate_per_sack >= 0", name="ck_products_rate_per_sack_non_negative"),
    )

    def __repr__(self):
        return f"<Product {self.name} ${self.rate_per_kg}/kg>"
