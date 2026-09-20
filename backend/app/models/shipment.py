import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ShipmentStatus(str, enum.Enum):
    LABEL_CREATED = "label_created"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    EXCEPTION = "exception"


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    tracking_number: Mapped[str] = mapped_column(String)
    status: Mapped[ShipmentStatus] = mapped_column(
        SAEnum(
            ShipmentStatus,
            name="shipment_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        )
    )
    carrier: Mapped[str] = mapped_column(String)
    origin: Mapped[str] = mapped_column(String)
    destination: Mapped[str] = mapped_column(String)
    estimated_delivery: Mapped[date] = mapped_column(Date)
    last_update: Mapped[datetime] = mapped_column(DateTime(timezone=True))
