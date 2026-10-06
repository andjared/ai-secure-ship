import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.chat_session import ChatSession, SessionState
from app.models.package import Package
from app.models.shipment import Shipment, ShipmentStatus
from app.services import admin_records, identity
from app.tools import lookup_shipments
from tests.conftest import JANE

JOHN = {
    "first_name": "John",
    "last_name": "Roe",
    "address": "9 Elm St, Denver, CO 80202",
    "phone_number": "555 987 6543",
}
SHIPMENT = {
    "tracking_number": "MX-ADMIN-0001",
    "status": ShipmentStatus.IN_TRANSIT,
    "carrier": "MockExpress",
    "origin": "Austin, TX",
    "destination": "Denver, CO",
    "estimated_delivery": date(2026, 10, 3),
}
PACKAGE = {
    "description": "Books",
    "weight_kg": Decimal("1.50"),
    "declared_value": Decimal("40.00"),
}
SHIPMENT_JSON = {
    **SHIPMENT,
    "status": "in_transit",
    "estimated_delivery": "2026-10-03",
}
PACKAGE_JSON = {"description": "Books", "weight_kg": "1.50", "declared_value": "40.00"}


def add_customer_with_shipment_and_package(db, details):
    customer = admin_records.create_customer(db, details)
    shipment = admin_records.create_shipment(db, customer.id, SHIPMENT)
    package = admin_records.create_package(db, shipment.id, PACKAGE)
    return customer, shipment, package


@pytest.fixture
def admin_client(client):
    yield client
    # Admin routes commit, so clear what they wrote to the test database.
    with SessionLocal() as db:
        db.execute(text("DELETE FROM packages"))
        db.execute(text("DELETE FROM shipments"))
        db.execute(text("DELETE FROM customers"))
        db.commit()


# --- service ---------------------------------------------------------------


def test_created_customer_passes_the_chat_identity_match(db):
    customer = admin_records.create_customer(db, JANE)

    assert identity.match_customer(db, **JANE) == customer.id


def test_update_customer_replaces_the_details(db):
    customer = admin_records.create_customer(db, JANE)

    updated = admin_records.update_customer(db, customer.id, JOHN)

    assert updated.id == customer.id
    assert updated.last_name == "Roe"
    assert [c.id for c in admin_records.list_customers(db)].count(customer.id) == 1


def test_changed_shipment_status_reaches_a_verified_chat_session(db):
    customer, shipment, _ = add_customer_with_shipment_and_package(db, JANE)
    session = ChatSession(state=SessionState.VERIFIED, customer_id=customer.id)

    admin_records.update_shipment(
        db, shipment.id, {**SHIPMENT, "status": ShipmentStatus.DELIVERED}
    )

    [seen] = lookup_shipments.list_customer_shipments(db, session)
    assert seen["status"] == "delivered"


def test_shipment_last_update_is_set_by_the_server(db):
    customer = admin_records.create_customer(db, JANE)
    shipment = admin_records.create_shipment(db, customer.id, SHIPMENT)
    shipment.last_update = datetime(2020, 1, 1, tzinfo=timezone.utc)

    admin_records.update_shipment(db, shipment.id, SHIPMENT)

    assert shipment.last_update.year > 2020


def test_update_package_replaces_the_details(db):
    _, shipment, package = add_customer_with_shipment_and_package(db, JANE)

    admin_records.update_package(
        db, package.id, {**PACKAGE, "description": "Lamp"}
    )

    [listed] = admin_records.list_packages(db, shipment.id)
    assert listed.description == "Lamp"


def test_shipment_for_unknown_customer_is_refused(db):
    assert admin_records.create_shipment(db, uuid.uuid4(), SHIPMENT) is None


def test_package_for_unknown_shipment_is_refused(db):
    assert admin_records.create_package(db, uuid.uuid4(), PACKAGE) is None


def test_unknown_ids_are_reported_as_missing(db):
    unknown = uuid.uuid4()

    assert admin_records.update_customer(db, unknown, JANE) is None
    assert admin_records.update_shipment(db, unknown, SHIPMENT) is None
    assert admin_records.update_package(db, unknown, PACKAGE) is None
    assert admin_records.delete_customer(db, unknown) is False
    assert admin_records.delete_shipment(db, unknown) is False
    assert admin_records.delete_package(db, unknown) is False


def test_delete_customer_removes_only_their_shipments_and_packages(db):
    jane, jane_shipment, jane_package = add_customer_with_shipment_and_package(
        db, JANE
    )
    john, john_shipment, john_package = add_customer_with_shipment_and_package(
        db, JOHN
    )

    assert admin_records.delete_customer(db, jane.id) is True

    db.expire_all()
    assert db.get(Shipment, jane_shipment.id) is None
    assert db.get(Package, jane_package.id) is None
    assert db.get(Shipment, john_shipment.id) is not None
    assert db.get(Package, john_package.id) is not None
    assert identity.match_customer(db, **JANE) is None
    assert identity.match_customer(db, **JOHN) == john.id


def test_list_shipments_covers_one_customer_or_all(db):
    _, jane_shipment, _ = add_customer_with_shipment_and_package(db, JANE)
    john, john_shipment, _ = add_customer_with_shipment_and_package(db, JOHN)

    every_id = [shipment.id for shipment in admin_records.list_shipments(db)]
    johns = admin_records.list_shipments(db, john.id)

    assert {jane_shipment.id, john_shipment.id} <= set(every_id)
    assert [shipment.id for shipment in johns] == [john_shipment.id]


def test_delete_shipment_removes_its_packages(db):
    customer, shipment, package = add_customer_with_shipment_and_package(db, JANE)

    assert admin_records.delete_shipment(db, shipment.id) is True

    db.expire_all()
    assert db.get(Package, package.id) is None
    assert admin_records.list_shipments(db, customer.id) == []


def test_delete_package_leaves_the_shipment(db):
    customer, shipment, package = add_customer_with_shipment_and_package(db, JANE)

    assert admin_records.delete_package(db, package.id) is True

    assert admin_records.list_packages(db, shipment.id) == []
    assert len(admin_records.list_shipments(db, customer.id)) == 1


def test_admin_logs_hold_no_customer_details(db, caplog):
    with caplog.at_level(logging.INFO):
        customer, _, _ = add_customer_with_shipment_and_package(db, JANE)
        admin_records.update_customer(db, customer.id, JOHN)
        admin_records.delete_customer(db, customer.id)

    assert "admin created customers" in caplog.text
    for detail in [*JANE.values(), *JOHN.values(), SHIPMENT["tracking_number"]]:
        assert detail not in caplog.text


# --- routes ----------------------------------------------------------------


def test_admin_routes_create_edit_and_delete_records(admin_client):
    customer = admin_client.post("/admin/customers", json=JANE)
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    shipment = admin_client.post(
        f"/admin/customers/{customer_id}/shipments", json=SHIPMENT_JSON
    )
    assert shipment.status_code == 201
    shipment_id = shipment.json()["id"]

    package = admin_client.post(
        f"/admin/shipments/{shipment_id}/packages", json=PACKAGE_JSON
    )
    assert package.status_code == 201

    edited = admin_client.put(
        f"/admin/shipments/{shipment_id}",
        json={**SHIPMENT_JSON, "status": "delivered"},
    )
    assert edited.json()["status"] == "delivered"
    listed = admin_client.get(
        "/admin/shipments", params={"customer_id": customer_id}
    ).json()
    assert [s["status"] for s in listed] == ["delivered"]

    assert admin_client.delete(f"/admin/customers/{customer_id}").status_code == 204
    assert admin_client.get("/admin/customers").json() == []
    assert admin_client.get(f"/admin/shipments/{shipment_id}/packages").json() == []


def test_list_shipments_route_rejects_a_malformed_customer_id(admin_client):
    response = admin_client.get(
        "/admin/shipments", params={"customer_id": "not-a-uuid"}
    )

    assert response.status_code == 422


def test_admin_routes_answer_404_for_unknown_records(admin_client):
    unknown = uuid.uuid4()

    responses = [
        admin_client.put(f"/admin/customers/{unknown}", json=JANE),
        admin_client.delete(f"/admin/customers/{unknown}"),
        admin_client.post(
            f"/admin/customers/{unknown}/shipments", json=SHIPMENT_JSON
        ),
        admin_client.delete(f"/admin/shipments/{unknown}"),
        admin_client.post(f"/admin/shipments/{unknown}/packages", json=PACKAGE_JSON),
        admin_client.delete(f"/admin/packages/{unknown}"),
    ]

    assert [response.status_code for response in responses] == [404] * 6


@pytest.mark.parametrize(
    "path, body",
    [
        ("/admin/customers", {**JANE, "first_name": "   "}),
        ("/admin/customers", {"first_name": "Jane"}),
        ("/admin/customers/{id}/shipments", {**SHIPMENT_JSON, "status": "lost"}),
        ("/admin/shipments/{id}/packages", {**PACKAGE_JSON, "weight_kg": "-1"}),
        ("/admin/shipments/{id}/packages", {**PACKAGE_JSON, "weight_kg": "10000"}),
    ],
)
def test_admin_routes_reject_invalid_input(admin_client, path, body):
    response = admin_client.post(path.format(id=uuid.uuid4()), json=body)

    assert response.status_code == 422
