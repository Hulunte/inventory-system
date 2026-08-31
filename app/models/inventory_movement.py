from datetime import datetime

from app.extensions import db


class InventoryMovement(db.Model):
    __tablename__ = "inventory_movements"

    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id"), nullable=False, index=True
    )

    movement_type = db.Column(db.String(20), nullable=False)

    quantity = db.Column(db.Integer, nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    product = db.relationship("Product", backref="inventory_movements")

    def __repr__(self):
        return f"<InventoryMovement " f"{self.movement_type} " f"{self.quantity}>"
