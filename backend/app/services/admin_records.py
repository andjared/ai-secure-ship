"""Create, edit and delete the records the chat draws from (Epic E2).

This module only touches customers, shipments and packages. It never reads or
writes a chat session, so nothing here can verify one (Epic E4).

Functions flush but do not commit; the caller owns the transaction. Logs carry
only the action, the record type and its id, never a record's contents.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.package import Package
from app.models.shipment import Shipment

logger = logging.getLogger(__name__)

AdminRecord = Customer | Shipment | Package


def _log(action: str, record: AdminRecord) -> None:
    logger.info("admin %s %s %s", action, record.__tablename__, record.id)


def _create(db: Session, record: AdminRecord) -> AdminRecord:
    db.add(record)
    db.flush()
    _log("created", record)
    return record


def _update(db: Session, record: AdminRecord | None, fields: dict):
    if record is None:
        return None
    for name, value in fields.items():
        setattr(record, name, value)
    db.flush()
    _log("updated", record)
    return record


def list_customers(db: Session) -> list[Customer]:
    return list(
        db.scalars(
            select(Customer).order_by(Customer.last_name, Customer.first_name)
        )
    )


def create_customer(db: Session, fields: dict) -> Customer:
    return _create(db, Customer(**fields))


def update_customer(
    db: Session, customer_id: uuid.UUID, fields: dict
) -> Customer | None:
    return _update(db, db.get(Customer, customer_id), fields)


def delete_customer(db: Session, customer_id: uuid.UUID) -> bool:
    """Delete a customer with their shipments and packages."""
    customer = db.get(Customer, customer_id)
    if customer is None:
        return False
    # The models define no cascade, so children go first.
    shipment_ids = select(Shipment.id).where(Shipment.customer_id == customer_id)
    db.execute(delete(Package).where(Package.shipment_id.in_(shipment_ids)))
    db.execute(delete(Shipment).where(Shipment.customer_id == customer_id))
    db.delete(customer)
    db.flush()
    _log("deleted", customer)
    return True


def list_shipments(
    db: Session, customer_id: uuid.UUID | None = None
) -> list[Shipment]:
    """One customer's shipments, or every shipment when no customer is given."""
    query = select(Shipment).order_by(Shipment.last_update.desc())
    if customer_id is not None:
        query = query.where(Shipment.customer_id == customer_id)
    return list(db.scalars(query))


def create_shipment(
    db: Session, customer_id: uuid.UUID, fields: dict
) -> Shipment | None:
    """Add a shipment to an existing customer; None if there is no such customer."""
    if db.get(Customer, customer_id) is None:
        return None
    return _create(
        db,
        Shipment(
            customer_id=customer_id,
            last_update=datetime.now(timezone.utc),
            **fields,
        ),
    )


def update_shipment(
    db: Session, shipment_id: uuid.UUID, fields: dict
) -> Shipment | None:
    # last_update is always set here, never taken from the admin.
    return _update(
        db,
        db.get(Shipment, shipment_id),
        {**fields, "last_update": datetime.now(timezone.utc)},
    )


def delete_shipment(db: Session, shipment_id: uuid.UUID) -> bool:
    """Delete a shipment with its packages."""
    shipment = db.get(Shipment, shipment_id)
    if shipment is None:
        return False
    db.execute(delete(Package).where(Package.shipment_id == shipment_id))
    db.delete(shipment)
    db.flush()
    _log("deleted", shipment)
    return True


def list_packages(db: Session, shipment_id: uuid.UUID) -> list[Package]:
    return list(
        db.scalars(
            select(Package)
            .where(Package.shipment_id == shipment_id)
            .order_by(Package.description)
        )
    )


def create_package(
    db: Session, shipment_id: uuid.UUID, fields: dict
) -> Package | None:
    """Add a package to an existing shipment; None if there is no such shipment."""
    if db.get(Shipment, shipment_id) is None:
        return None
    return _create(db, Package(shipment_id=shipment_id, **fields))


def update_package(
    db: Session, package_id: uuid.UUID, fields: dict
) -> Package | None:
    return _update(db, db.get(Package, package_id), fields)


def delete_package(db: Session, package_id: uuid.UUID) -> bool:
    package = db.get(Package, package_id)
    if package is None:
        return False
    db.delete(package)
    db.flush()
    _log("deleted", package)
    return True
