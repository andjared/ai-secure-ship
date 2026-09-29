import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.llm import ollama_client
from app.llm.system_prompt import VERIFIED_SHIPMENTS_PROMPT
from app.models.chat_session import ChatSession, SessionState
from app.models.customer import Customer
from app.models.package import Package
from app.models.shipment import Shipment, ShipmentStatus
from app.tools import lookup_shipments
from app.tools.lookup_shipments import (
    LOOKUP_SHIPMENTS_TOOL,
    TOOL_NAME,
    TOOL_UNAVAILABLE_RESULT,
)
from tests.conftest import JANE

JOHN = {
    "first_name": "John",
    "last_name": "Roe",
    "address": "9 Elm St, Denver, CO 80202",
    "phone_number": "555 987 6543",
}
JANE_TRACKING = "MX-JANE-0001"
JOHN_TRACKING = "MX-JOHN-0001"


def add_customer_with_shipment(db, details, tracking_number) -> uuid.UUID:
    customer = Customer(**details)
    db.add(customer)
    db.flush()
    shipment = Shipment(
        customer_id=customer.id,
        tracking_number=tracking_number,
        status=ShipmentStatus.IN_TRANSIT,
        carrier="MockExpress",
        origin="Austin, TX",
        destination="Denver, CO",
        estimated_delivery=date(2026, 10, 3),
        last_update=datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc),
    )
    db.add(shipment)
    db.flush()
    db.add(
        Package(
            shipment_id=shipment.id,
            description="Books",
            weight_kg=Decimal("1.50"),
            declared_value=Decimal("40.00"),
        )
    )
    return customer.id


@pytest.fixture
def customers():
    """Jane and John, one shipment each. Committed, since routes use their
    own DB session."""
    with SessionLocal() as db:
        ids = {
            "jane": add_customer_with_shipment(db, JANE, JANE_TRACKING),
            "john": add_customer_with_shipment(db, JOHN, JOHN_TRACKING),
        }
        db.commit()
    yield ids
    with SessionLocal() as db:
        for statement in (
            "DELETE FROM packages WHERE shipment_id IN "
            "(SELECT id FROM shipments WHERE customer_id = ANY(:ids))",
            "DELETE FROM shipments WHERE customer_id = ANY(:ids)",
            "DELETE FROM customers WHERE id = ANY(:ids)",
        ):
            db.execute(text(statement), {"ids": list(ids.values())})
        db.commit()


def tracking_numbers(result: dict) -> list[str]:
    return [shipment["tracking_number"] for shipment in result["shipments"]]


# --- run_tool: the enforcement point ----------------------------------------


def test_verified_session_gets_only_its_own_shipments(db, customers):
    session = ChatSession(
        state=SessionState.VERIFIED, customer_id=customers["jane"]
    )

    result = lookup_shipments.run_tool(db, session, TOOL_NAME, {})

    assert tracking_numbers(result) == [JANE_TRACKING]
    shipment = result["shipments"][0]
    assert shipment["status"] == "in_transit"
    assert shipment["estimated_delivery"] == "2026-10-03"
    assert shipment["packages"] == [
        {"description": "Books", "weight_kg": "1.50", "declared_value": "40.00"}
    ]
    assert "customer_id" not in shipment


def test_model_supplied_arguments_are_ignored(db, customers):
    session = ChatSession(
        state=SessionState.VERIFIED, customer_id=customers["jane"]
    )
    arguments = {
        "customer_id": str(customers["john"]),
        "tracking_number": JOHN_TRACKING,
        "all": True,
    }

    result = lookup_shipments.run_tool(db, session, TOOL_NAME, arguments)

    assert tracking_numbers(result) == [JANE_TRACKING]


@pytest.mark.parametrize(
    "state",
    [
        SessionState.ANONYMOUS,
        SessionState.COLLECTING_IDENTITY,
        SessionState.CODE_SENT,
        SessionState.AWAITING_CODE,
        SessionState.ESCALATED_TO_HUMAN,
    ],
)
def test_unverified_session_is_refused(db, customers, state):
    # Even with a customer id somehow set, only VERIFIED may look up.
    session = ChatSession(state=state, customer_id=customers["jane"])

    result = lookup_shipments.run_tool(
        db, session, TOOL_NAME, {"customer_id": str(customers["jane"])}
    )

    assert result == TOOL_UNAVAILABLE_RESULT


def test_verified_session_without_customer_is_refused(db, customers):
    session = ChatSession(state=SessionState.VERIFIED, customer_id=None)

    result = lookup_shipments.run_tool(db, session, TOOL_NAME, {})

    assert result == TOOL_UNAVAILABLE_RESULT


def test_unknown_tool_is_refused(db, customers):
    session = ChatSession(
        state=SessionState.VERIFIED, customer_id=customers["jane"]
    )

    result = lookup_shipments.run_tool(db, session, "lookup_all_shipments", {})

    assert result == TOOL_UNAVAILABLE_RESULT


def test_tool_definition_takes_no_arguments():
    assert LOOKUP_SHIPMENTS_TOOL["function"]["name"] == TOOL_NAME
    assert LOOKUP_SHIPMENTS_TOOL["function"]["parameters"]["properties"] == {}


# --- ollama_client.chat: the tool-call loop ----------------------------------


def tool_call_reply(name=TOOL_NAME, arguments=None) -> dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"function": {"name": name, "arguments": arguments or {}}}
        ],
    }


@pytest.fixture
def scripted_model(monkeypatch):
    """Replace the HTTP call; each call pops the next scripted reply."""
    payloads: list[dict] = []
    replies: list[dict] = []

    def fake_post_chat(payload):
        # Copy, since chat() keeps appending to the same messages list.
        payloads.append({**payload, "messages": list(payload["messages"])})
        return replies.pop(0)

    monkeypatch.setattr(ollama_client, "_post_chat", fake_post_chat)
    return payloads, replies


def test_tool_result_is_sent_back_to_the_model(scripted_model):
    payloads, replies = scripted_model
    replies.extend(
        [
            tool_call_reply(arguments={"customer_id": "someone"}),
            {"role": "assistant", "content": "It's in transit."},
        ]
    )
    calls = []

    def run_tool(name, arguments):
        calls.append((name, arguments))
        return {"shipments": []}

    reply = ollama_client.chat(
        "where is my package?", tools=[LOOKUP_SHIPMENTS_TOOL], run_tool=run_tool
    )

    assert reply == "It's in transit."
    assert calls == [(TOOL_NAME, {"customer_id": "someone"})]
    assert payloads[0]["tools"] == [LOOKUP_SHIPMENTS_TOOL]
    tool_message = payloads[1]["messages"][-1]
    assert tool_message == {
        "role": "tool",
        "tool_name": TOOL_NAME,
        "content": '{"shipments": []}',
    }


def test_tool_result_reaches_the_model_unescaped(scripted_model):
    payloads, replies = scripted_model
    replies.extend(
        [tool_call_reply(), {"role": "assistant", "content": "done"}]
    )

    ollama_client.chat(
        "hi",
        tools=[LOOKUP_SHIPMENTS_TOOL],
        run_tool=lambda name, args: {"destination": "Čačak"},
    )

    assert payloads[1]["messages"][-1]["content"] == '{"destination": "Čačak"}'


def test_endless_tool_calls_stop_at_the_cap(scripted_model):
    payloads, replies = scripted_model
    replies.extend(
        [tool_call_reply() for _ in range(ollama_client.MAX_TOOL_ROUNDS + 1)]
    )

    reply = ollama_client.chat(
        "hi", tools=[LOOKUP_SHIPMENTS_TOOL], run_tool=lambda name, args: {}
    )

    assert reply == ollama_client.TOOL_ROUNDS_EXCEEDED_MESSAGE
    assert len(payloads) == ollama_client.MAX_TOOL_ROUNDS + 1


def test_no_tools_are_sent_when_none_are_given(scripted_model):
    payloads, replies = scripted_model
    replies.append({"role": "assistant", "content": "Hello!"})

    assert ollama_client.chat("hi") == "Hello!"
    assert "tools" not in payloads[0]


# --- /chat --------------------------------------------------------------------


def add_session(**fields) -> str:
    with SessionLocal() as db:
        session = ChatSession(transcript=[], pending_identity={}, **fields)
        db.add(session)
        db.commit()
        return str(session.id)


def load_session(session_id) -> ChatSession:
    with SessionLocal() as db:
        return db.get(ChatSession, session_id)


def test_verified_chat_offers_the_tool_and_records_the_call(
    client, fake_model, customers
):
    session_id = add_session(
        state=SessionState.VERIFIED, customer_id=customers["jane"]
    )
    fake_model.tool_call = (TOOL_NAME, {"customer_id": str(customers["john"])})

    response = client.post(
        "/chat",
        json={"message": "where is my package?", "session_id": session_id},
    )

    assert response.status_code == 200
    seen = fake_model.replies_seen[-1]
    assert seen["tools"] == [LOOKUP_SHIPMENTS_TOOL]
    assert VERIFIED_SHIPMENTS_PROMPT in seen["extra_instructions"]
    assert tracking_numbers(fake_model.tool_results[0]) == [JANE_TRACKING]
    assistant_turn = load_session(session_id).transcript[-1]
    assert assistant_turn["tool_calls"] == [TOOL_NAME]


def test_anonymous_chat_is_offered_no_tools(client, fake_model, customers):
    fake_model.extraction = {"asks_about_shipment": False}
    fake_model.tool_call = (TOOL_NAME, {})

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    seen = fake_model.replies_seen[-1]
    assert seen["tools"] is None
    assert VERIFIED_SHIPMENTS_PROMPT not in (seen["extra_instructions"] or "")
    # Even if the model calls the tool anyway, the backend refuses it.
    assert fake_model.tool_results == [TOOL_UNAVAILABLE_RESULT]
