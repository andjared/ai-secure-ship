import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.shipment import ShipmentStatus
from app.services import admin_records

# Every admin route hangs off this one router, so access control is attached
# in a single place.
router = APIRouter(prefix="/admin", tags=["admin"])

Text = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class CustomerInput(BaseModel):
    first_name: Text
    last_name: Text
    phone_number: Text
    address: Text


class CustomerRecord(CustomerInput):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class ShipmentInput(BaseModel):
    tracking_number: Text
    status: ShipmentStatus
    carrier: Text
    origin: Text
    destination: Text
    estimated_delivery: date


class ShipmentRecord(ShipmentInput):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    last_update: datetime


class PackageInput(BaseModel):
    description: Text
    # The limits match the Numeric(6, 2) and Numeric(10, 2) columns.
    weight_kg: Decimal = Field(gt=0, max_digits=6, decimal_places=2)
    declared_value: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class PackageRecord(PackageInput):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shipment_id: uuid.UUID


Found = TypeVar("Found")


def _require_found(result: Found | None) -> Found:
    """Turn the service's "no such record" (None or False) into a 404."""
    if not result:
        raise HTTPException(status_code=404, detail="Record not found")
    return result


@router.get("/customers", operation_id="listCustomers")
def list_customers(db: Session = Depends(get_db)) -> list[CustomerRecord]:
    return admin_records.list_customers(db)


@router.post("/customers", operation_id="createCustomer", status_code=201)
def create_customer(
    request: CustomerInput, db: Session = Depends(get_db)
) -> CustomerRecord:
    customer = admin_records.create_customer(db, request.model_dump())
    db.commit()
    return customer


@router.put("/customers/{customer_id}", operation_id="updateCustomer")
def update_customer(
    customer_id: uuid.UUID, request: CustomerInput, db: Session = Depends(get_db)
) -> CustomerRecord:
    customer = _require_found(
        admin_records.update_customer(db, customer_id, request.model_dump())
    )
    db.commit()
    return customer


@router.delete(
    "/customers/{customer_id}", operation_id="deleteCustomer", status_code=204
)
def delete_customer(customer_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    _require_found(admin_records.delete_customer(db, customer_id))
    db.commit()


@router.get("/shipments", operation_id="listShipments")
def list_shipments(
    customer_id: uuid.UUID | None = None, db: Session = Depends(get_db)
) -> list[ShipmentRecord]:
    return admin_records.list_shipments(db, customer_id)


@router.post(
    "/customers/{customer_id}/shipments",
    operation_id="createShipment",
    status_code=201,
)
def create_shipment(
    customer_id: uuid.UUID, request: ShipmentInput, db: Session = Depends(get_db)
) -> ShipmentRecord:
    shipment = _require_found(
        admin_records.create_shipment(db, customer_id, request.model_dump())
    )
    db.commit()
    return shipment


@router.put("/shipments/{shipment_id}", operation_id="updateShipment")
def update_shipment(
    shipment_id: uuid.UUID, request: ShipmentInput, db: Session = Depends(get_db)
) -> ShipmentRecord:
    shipment = _require_found(
        admin_records.update_shipment(db, shipment_id, request.model_dump())
    )
    db.commit()
    return shipment


@router.delete(
    "/shipments/{shipment_id}", operation_id="deleteShipment", status_code=204
)
def delete_shipment(shipment_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    _require_found(admin_records.delete_shipment(db, shipment_id))
    db.commit()


@router.get("/shipments/{shipment_id}/packages", operation_id="listPackages")
def list_packages(
    shipment_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[PackageRecord]:
    return admin_records.list_packages(db, shipment_id)


@router.post(
    "/shipments/{shipment_id}/packages",
    operation_id="createPackage",
    status_code=201,
)
def create_package(
    shipment_id: uuid.UUID, request: PackageInput, db: Session = Depends(get_db)
) -> PackageRecord:
    package = _require_found(
        admin_records.create_package(db, shipment_id, request.model_dump())
    )
    db.commit()
    return package


@router.put("/packages/{package_id}", operation_id="updatePackage")
def update_package(
    package_id: uuid.UUID, request: PackageInput, db: Session = Depends(get_db)
) -> PackageRecord:
    package = _require_found(
        admin_records.update_package(db, package_id, request.model_dump())
    )
    db.commit()
    return package


@router.delete(
    "/packages/{package_id}", operation_id="deletePackage", status_code=204
)
def delete_package(package_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    _require_found(admin_records.delete_package(db, package_id))
    db.commit()
