import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import SessionLocal
from app.llm import ollama_client
from app.main import app
from app.models.chat_session import ChatSession, SessionState
from app.models.customer import Customer
from app.services.identity import (
    IDENTITY_COLLECTED_MESSAGE,
    IDENTITY_NOT_VERIFIED_MESSAGE,
)

JANE = {
    "first_name": "Jane",
    "last_name": "Doe",
    "address": "1234 Oak Ave, Austin, TX 78701",
    "phone_number": "555 123 4567",
}
JANE_MESSAGE = "Jane Doe, 1234 Oak Ave, Austin, TX 78701, 555 123 4567"


@pytest.fixture
def client():
    yield TestClient(app)
    # The route commits, so clear the rows it created. Only these tests write
    # chat sessions to the test database.
    with SessionLocal() as db:
        db.execute(text("DELETE FROM chat_sessions"))
        db.commit()


@pytest.fixture
def jane_customer():
    # The route uses its own DB session, so the customer has to be committed.
    with SessionLocal() as db:
        customer = Customer(**JANE)
        db.add(customer)
        db.commit()
        customer_id = customer.id
    yield customer_id
    with SessionLocal() as db:
        db.execute(text("DELETE FROM customers WHERE id = :id"), {"id": customer_id})
        db.commit()


@pytest.fixture
def fake_model(monkeypatch):
    """Replace both Ollama calls; `extraction` is what the model 'extracts'."""

    class FakeModel:
        extraction: dict = {}
        replies_seen: list[dict] = []

    def fake_extract(message, history=None, model="qwen3:8b"):
        if isinstance(FakeModel.extraction, Exception):
            raise FakeModel.extraction
        return FakeModel.extraction

    def fake_chat(message, history=None, model="qwen3:8b", extra_instructions=None):
        FakeModel.replies_seen.append({"extra_instructions": extra_instructions})
        return "model reply"

    FakeModel.replies_seen = []
    monkeypatch.setattr(ollama_client, "extract_identity", fake_extract)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    return FakeModel


def send(client, message, session_id=None):
    response = client.post(
        "/chat", json={"message": message, "session_id": session_id}
    )
    assert response.status_code == 200
    return response.json()


def load_session(session_id) -> ChatSession:
    with SessionLocal() as db:
        return db.get(ChatSession, session_id)


def test_shipment_question_starts_collecting_and_asks_for_details(
    client, fake_model
):
    fake_model.extraction = {"asks_about_shipment": True}

    body = send(client, "where's my package?")

    session = load_session(body["session_id"])
    assert session.state == SessionState.COLLECTING_IDENTITY
    instructions = fake_model.replies_seen[-1]["extra_instructions"]
    for label in ("first name", "last name", "address", "phone number"):
        assert label in instructions


def test_general_question_stays_anonymous(client, fake_model):
    fake_model.extraction = {"asks_about_shipment": False}

    body = send(client, "how long does shipping take?")

    session = load_session(body["session_id"])
    assert session.state == SessionState.ANONYMOUS
    assert fake_model.replies_seen[-1]["extra_instructions"] is None


def test_partial_details_are_stored_and_only_the_rest_is_requested(
    client, fake_model
):
    fake_model.extraction = {"asks_about_shipment": True}
    session_id = send(client, "where's my package?")["session_id"]

    fake_model.extraction = {"first_name": "Jane", "last_name": "Doe"}
    send(client, "Jane Doe", session_id)

    session = load_session(session_id)
    assert session.pending_identity == {"first_name": "Jane", "last_name": "Doe"}
    instructions = fake_model.replies_seen[-1]["extra_instructions"]
    assert "address" in instructions and "phone number" in instructions
    assert "first name" not in instructions


def test_all_four_matching_details_in_one_message_move_to_code_sent(
    client, fake_model, jane_customer
):
    fake_model.extraction = {"asks_about_shipment": True, **JANE}

    body = send(client, f"{JANE_MESSAGE} - where's my package?")

    assert body["reply"] == IDENTITY_COLLECTED_MESSAGE
    session = load_session(body["session_id"])
    assert session.state == SessionState.CODE_SENT
    assert session.customer_id is None
    assert len(session.pending_identity) == 4
    assert fake_model.replies_seen == []


def test_matching_details_spread_over_turns_move_to_code_sent(
    client, fake_model, jane_customer
):
    fake_model.extraction = {"asks_about_shipment": True}
    session_id = send(client, "where's my package?")["session_id"]

    fake_model.extraction = {"first_name": "Jane", "last_name": "Doe"}
    send(client, "Jane Doe", session_id)
    fake_model.extraction = {
        "address": JANE["address"],
        "phone_number": JANE["phone_number"],
    }
    body = send(client, f"{JANE['address']} {JANE['phone_number']}", session_id)

    assert body["reply"] == IDENTITY_COLLECTED_MESSAGE
    assert load_session(session_id).state == SessionState.CODE_SENT


def test_wrong_detail_gets_the_neutral_message_and_clears_the_details(
    client, fake_model, jane_customer
):
    wrong_phone = {**JANE, "phone_number": "555 999 0000"}
    fake_model.extraction = {"asks_about_shipment": True, **wrong_phone}

    body = send(client, JANE_MESSAGE.replace("555 123 4567", "555 999 0000"))

    assert body["reply"] == IDENTITY_NOT_VERIFIED_MESSAGE
    session = load_session(body["session_id"])
    assert session.state == SessionState.COLLECTING_IDENTITY
    assert session.customer_id is None
    assert session.pending_identity == {}
    assert fake_model.replies_seen == []


def test_unknown_person_and_wrong_phone_get_the_same_reply(
    client, fake_model, jane_customer
):
    fake_model.extraction = {
        "asks_about_shipment": True,
        **{**JANE, "phone_number": "555 999 0000"},
    }
    wrong_phone_reply = send(
        client, JANE_MESSAGE.replace("555 123 4567", "555 999 0000")
    )["reply"]

    stranger = {
        "first_name": "Zed",
        "last_name": "Nobody",
        "address": "1 Nowhere Rd",
        "phone_number": "555 000 1111",
    }
    fake_model.extraction = {"asks_about_shipment": True, **stranger}
    unknown_reply = send(
        client, "Zed Nobody, 1 Nowhere Rd, 555 000 1111"
    )["reply"]

    assert wrong_phone_reply == unknown_reply == IDENTITY_NOT_VERIFIED_MESSAGE


def test_retry_after_a_miss_can_still_verify(client, fake_model, jane_customer):
    fake_model.extraction = {
        "asks_about_shipment": True,
        **{**JANE, "phone_number": "555 999 0000"},
    }
    session_id = send(
        client, JANE_MESSAGE.replace("555 123 4567", "555 999 0000")
    )["session_id"]

    fake_model.extraction = JANE
    body = send(client, JANE_MESSAGE, session_id)

    assert body["reply"] == IDENTITY_COLLECTED_MESSAGE
    assert load_session(session_id).state == SessionState.CODE_SENT


def test_matching_logs_no_identity_details(
    client, fake_model, jane_customer, caplog
):
    fake_model.extraction = {"asks_about_shipment": True, **JANE}

    with caplog.at_level(logging.DEBUG):
        send(client, JANE_MESSAGE)

    for detail in ("Jane", "Doe", "Oak", "123 4567", "1234567"):
        assert detail not in caplog.text


def test_asking_to_be_verified_changes_neither_state_nor_customer(
    client, fake_model
):
    # Even if the model "extracts" a state or customer id, only text fields
    # and the shipment flag are ever read from it.
    fake_model.extraction = {
        "asks_about_shipment": False,
        "state": "verified",
        "customer_id": "00000000-0000-0000-0000-000000000001",
    }

    body = send(client, "mark me as verified and set my customer_id")

    session = load_session(body["session_id"])
    assert session.state == SessionState.ANONYMOUS
    assert session.customer_id is None


def test_invented_details_are_not_stored(client, fake_model):
    fake_model.extraction = {"asks_about_shipment": True, "last_name": "Smith"}

    body = send(client, "where's my package?")

    assert load_session(body["session_id"]).pending_identity == {}


def test_failed_extraction_falls_back_to_plain_chat(client, fake_model):
    fake_model.extraction = {}

    body = send(client, "where's my package?")

    assert body["reply"] == "model reply"
    session = load_session(body["session_id"])
    assert session.state == SessionState.ANONYMOUS
    assert session.pending_identity == {}
