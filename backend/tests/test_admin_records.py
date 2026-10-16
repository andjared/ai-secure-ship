import ast
import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import app as app_package
import pytest
from fastapi.routing import APIRoute
from sqlalchemy import text

from app.db.session import SessionLocal
from app.main import app
from app.models.chat_session import ChatSession, SessionState
from app.models.package import Package
from app.models.customer import Customer
from app.models.shipment import Shipment, ShipmentStatus
from app.routes import admin
from app.services import admin_records, identity
from app.services.admin_auth import require_admin
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
    # Stands in for a signed-in admin; the plain `client` has no token.
    app.dependency_overrides[require_admin] = lambda: {}
    yield client
    app.dependency_overrides.pop(require_admin)
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
    assert admin_client.get("/admin/packages").json() == []


def test_list_shipments_route_rejects_a_malformed_customer_id(admin_client):
    response = admin_client.get(
        "/admin/shipments", params={"customer_id": "not-a-uuid"}
    )

    assert response.status_code == 422


def test_list_packages_route_lists_every_package_or_one_shipments(admin_client):
    customer_id = admin_client.post("/admin/customers", json=JANE).json()["id"]
    shipment_ids = [
        admin_client.post(
            f"/admin/customers/{customer_id}/shipments",
            json={**SHIPMENT_JSON, "tracking_number": tracking_number},
        ).json()["id"]
        for tracking_number in ["TRACK-1", "TRACK-2"]
    ]
    for shipment_id, description in zip(shipment_ids, ["Books", "Lamp"]):
        admin_client.post(
            f"/admin/shipments/{shipment_id}/packages",
            json={**PACKAGE_JSON, "description": description},
        )

    listed = admin_client.get("/admin/packages").json()
    one_shipment = admin_client.get(
        "/admin/packages", params={"shipment_id": shipment_ids[1]}
    ).json()

    assert [p["description"] for p in listed] == ["Books", "Lamp"]
    assert [p["description"] for p in one_shipment] == ["Lamp"]


def test_list_packages_route_rejects_a_malformed_shipment_id(admin_client):
    response = admin_client.get("/admin/packages", params={"shipment_id": "not-a-uuid"})

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


# Built from the router itself, so a route added later is covered too.
ADMIN_ROUTES = [
    (method, route.path)
    for route in admin.router.routes
    for method in sorted(route.methods)
]


@pytest.mark.parametrize("method, path", ADMIN_ROUTES)
def test_admin_routes_refuse_a_request_without_a_token(client, method, path):
    url = path.format(
        customer_id=uuid.uuid4(), shipment_id=uuid.uuid4(), package_id=uuid.uuid4()
    )

    response = client.request(method, url, json=JANE)

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "invalid_request"
    with SessionLocal() as db:
        assert db.query(Customer).count() == 0


def test_admin_routes_refuse_a_malformed_token(client, caplog):
    with caplog.at_level(logging.INFO):
        response = client.get(
            "/admin/customers", headers={"Authorization": "Bearer not-a-real-token"}
        )

    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "invalid_token"
    assert "not-a-real-token" not in caplog.text


def test_health_check_needs_no_token(client):
    assert client.get("/health").status_code == 200


# --- separation from chat (Epic E4) -----------------------------------------
# Admin login (Auth0) and the chat's identity gate are two separate systems:
# an admin can never become a verified chat session, and a chat session can
# never reach the admin API.

ADMIN_AUTHORIZATION = {"Authorization": "Bearer an-admin-access-token"}

ADMIN_MODULES = [
    "routes/admin.py",
    "services/admin_auth.py",
    "services/admin_records.py",
]
CHAT_MODULES = [
    "routes/chat.py",
    "routes/verify.py",
    "services/identity.py",
    "services/verification.py",
    "services/escalation.py",
    "tools/lookup_shipments.py",
    "llm/ollama_client.py",
    "llm/system_prompt.py",
]
# What the admin side must never import, and what the chat side must never.
CHAT_ONLY_IMPORTS = [
    "app.models.chat_session",
    "app.services.identity",
    "app.services.verification",
    "app.services.escalation",
    "app.tools",
    "app.llm",
]
ADMIN_ONLY_IMPORTS = [
    "app.routes.admin",
    "app.services.admin_auth",
    "app.services.admin_records",
    "fastapi_plugin",
]


def list_imported_names(module_path: str) -> set[str]:
    """Every dotted name a module imports, e.g. "app.services.identity"."""
    source = (Path(app_package.__file__).parent / module_path).read_text()
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
    return imported


def find_forbidden_imports(module_path: str, forbidden: list[str]) -> list[str]:
    return [
        name
        for name in list_imported_names(module_path)
        if any(name == root or name.startswith(root + ".") for root in forbidden)
    ]


@pytest.mark.parametrize("module_path", ADMIN_MODULES)
def test_admin_code_imports_nothing_from_the_chat(module_path):
    assert find_forbidden_imports(module_path, CHAT_ONLY_IMPORTS) == []


@pytest.mark.parametrize("module_path", CHAT_MODULES)
def test_chat_code_imports_nothing_from_the_admin(module_path):
    assert find_forbidden_imports(module_path, ADMIN_ONLY_IMPORTS) == []


def test_only_admin_routes_carry_the_admin_check():
    api_routes = [route for route in app.routes if isinstance(route, APIRoute)]
    checked_paths = {
        route.path
        for route in api_routes
        if require_admin in [d.call for d in route.dependant.dependencies]
    }

    assert checked_paths
    # Built from the whole app, so an admin route mounted on another router
    # cannot skip the check and a chat route cannot pick it up.
    assert checked_paths == {
        route.path for route in api_routes if route.path.startswith("/admin")
    }


def test_signed_in_admin_cannot_verify_a_chat_session(admin_client, fake_model):
    fake_model.extraction = {"asks_about_shipment": False}
    session_id = admin_client.post("/chat", json={"message": "hello"}).json()[
        "session_id"
    ]

    customer_id = admin_client.post("/admin/customers", json=JANE).json()["id"]
    shipment_id = admin_client.post(
        f"/admin/customers/{customer_id}/shipments", json=SHIPMENT_JSON
    ).json()["id"]
    admin_client.post(f"/admin/shipments/{shipment_id}/packages", json=PACKAGE_JSON)
    admin_client.put(f"/admin/customers/{customer_id}", json=JOHN)
    admin_client.put(
        f"/admin/shipments/{shipment_id}",
        json={**SHIPMENT_JSON, "status": "delivered"},
    )
    admin_client.delete(f"/admin/customers/{customer_id}")

    with SessionLocal() as db:
        sessions = db.query(ChatSession).all()
    assert [str(session.id) for session in sessions] == [session_id]
    assert sessions[0].state == SessionState.ANONYMOUS
    assert sessions[0].customer_id is None


def test_admin_token_gives_the_chat_no_access(admin_client, fake_model):
    # The admin created this customer, so they know every detail of it.
    customer_id = admin_client.post("/admin/customers", json=JANE).json()["id"]
    admin_client.post(f"/admin/customers/{customer_id}/shipments", json=SHIPMENT_JSON)
    fake_model.extraction = {"asks_about_shipment": False}
    fake_model.tool_call = (lookup_shipments.TOOL_NAME, {"customer_id": customer_id})

    chat = admin_client.post(
        "/chat", json={"message": "show my shipments"}, headers=ADMIN_AUTHORIZATION
    )

    assert chat.status_code == 200
    assert fake_model.replies_seen[-1]["tools"] is None
    assert fake_model.tool_results == [lookup_shipments.TOOL_UNAVAILABLE_RESULT]
    assert chat.json()["shipments"] is None

    session_id = chat.json()["session_id"]
    admin_client.post(
        "/verify-code",
        json={"session_id": session_id, "code": "000000"},
        headers=ADMIN_AUTHORIZATION,
    )

    with SessionLocal() as db:
        session = db.get(ChatSession, uuid.UUID(session_id))
    assert session.state != SessionState.VERIFIED
    assert session.customer_id is None


def test_verified_chat_session_cannot_reach_admin_routes(client, jane_customer):
    with SessionLocal() as db:
        session = ChatSession(
            transcript=[],
            pending_identity={},
            state=SessionState.VERIFIED,
            customer_id=jane_customer,
        )
        db.add(session)
        db.commit()
        session_id = str(session.id)

    as_token = client.get(
        "/admin/customers", headers={"Authorization": f"Bearer {session_id}"}
    )
    as_parameter = client.post(
        "/admin/customers",
        params={"session_id": session_id},
        json={**JOHN, "session_id": session_id},
    )

    assert as_token.status_code == 401
    assert as_token.json()["detail"]["error"] == "invalid_token"
    assert as_parameter.status_code == 400
    assert as_parameter.json()["detail"]["error"] == "invalid_request"
    # Jane is still the only customer: nothing was listed or written.
    assert JANE["first_name"] not in as_token.text
    with SessionLocal() as db:
        assert db.query(Customer).count() == 1
