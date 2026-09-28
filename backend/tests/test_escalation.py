import uuid

import pytest

from app.db.session import SessionLocal
from app.llm.system_prompt import HUMAN_HANDOFF_PROMPT
from app.models.chat_session import ChatSession, SessionState
from app.services import escalation
from tests.conftest import JANE

HUMAN_REQUEST = "I want to talk to a human"


def send(client, message, session_id=None):
    response = client.post(
        "/chat", json={"message": message, "session_id": session_id}
    )
    assert response.status_code == 200
    return response.json()


def load_session(session_id) -> ChatSession:
    with SessionLocal() as db:
        return db.get(ChatSession, session_id)


def add_session(**fields) -> str:
    # Routes use their own DB session, so the row has to be committed.
    with SessionLocal() as db:
        session = ChatSession(transcript=[], **fields)
        db.add(session)
        db.commit()
        return str(session.id)


def refuse_model_calls(fake_model):
    """Make any Ollama call fail the request, proving none was made."""
    fake_model.extraction = RuntimeError("extraction must not run")


# --- is_asking_for_human -----------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "I want to talk to a human",
        "can I speak to a real person?",
        "Please connect me with an agent",
        "transfer me to a representative",
    ],
)
def test_requests_for_a_human_are_recognized(message):
    assert escalation.is_asking_for_human(message)


@pytest.mark.parametrize(
    "message",
    [
        "is a human handling my package?",
        "where's my package?",
        "how long does shipping take?",
    ],
)
def test_other_messages_are_not_escalation_requests(message):
    assert not escalation.is_asking_for_human(message)


# --- build_greeting ----------------------------------------------------------


def test_greeting_uses_the_first_name_the_visitor_gave():
    assert "Jane" in escalation.build_greeting({"first_name": "Jane"})


def test_greeting_without_a_first_name_is_nameless():
    assert escalation.build_greeting({}) == (
        "Hey, I'm up to speed, how can I help?"
    )


# --- /chat -------------------------------------------------------------------


def test_escalation_from_anonymous_plays_the_script_without_changing_state(
    client, fake_model
):
    refuse_model_calls(fake_model)

    body = send(client, HUMAN_REQUEST)

    assert body["event"] == "escalated_to_human"
    assert [line["kind"] for line in body["handoff"]] == [
        "assistant",
        "system",
        "assistant",
        "assistant",
    ]
    assert [line["content"] for line in body["handoff"]] == [
        escalation.ESCALATION_ACK_MESSAGE,
        escalation.HUMAN_JOINED_MESSAGE,
        escalation.HUMAN_READING_MESSAGE,
        escalation.build_greeting({}),
    ]
    assert body["reply"] == escalation.ESCALATION_ACK_MESSAGE
    assert fake_model.replies_seen == []

    session = load_session(body["session_id"])
    assert session.state == SessionState.ANONYMOUS
    assert session.customer_id is None
    scripted_turns = [
        turn
        for turn in session.transcript
        if turn.get("event") == escalation.ESCALATION_EVENT
    ]
    assert len(scripted_turns) == 4


def test_escalation_from_verified_keeps_the_verified_customer(
    client, fake_model
):
    refuse_model_calls(fake_model)
    customer_id = uuid.uuid4()
    session_id = add_session(
        state=SessionState.VERIFIED,
        customer_id=customer_id,
        pending_identity=dict(JANE),
    )

    body = send(client, HUMAN_REQUEST, session_id)

    assert body["event"] == "escalated_to_human"
    assert body["handoff"][-1]["content"] == escalation.build_greeting(JANE)
    session = load_session(session_id)
    assert session.state == SessionState.VERIFIED
    assert session.customer_id == customer_id


def test_escalation_mid_collection_keeps_the_details_given_so_far(
    client, fake_model
):
    refuse_model_calls(fake_model)
    session_id = add_session(
        state=SessionState.COLLECTING_IDENTITY,
        pending_identity={"first_name": "Jane"},
    )

    body = send(client, HUMAN_REQUEST, session_id)

    assert "Jane" in body["handoff"][-1]["content"]
    session = load_session(session_id)
    assert session.state == SessionState.COLLECTING_IDENTITY
    assert session.pending_identity == {"first_name": "Jane"}


def test_asking_again_gets_one_short_line(client, fake_model):
    refuse_model_calls(fake_model)
    session_id = send(client, HUMAN_REQUEST)["session_id"]

    body = send(client, HUMAN_REQUEST, session_id)

    assert body["handoff"] == [
        {
            "kind": "assistant",
            "content": escalation.ALREADY_WITH_HUMAN_MESSAGE,
        }
    ]


def test_escalated_visitor_still_goes_through_the_identity_gate(
    client, fake_model
):
    # Epic G4: "Melany" is no way around the gate.
    session_id = send(client, HUMAN_REQUEST)["session_id"]

    fake_model.extraction = {"asks_about_shipment": True}
    body = send(client, "Melany, where's my package?", session_id)

    assert body["event"] is None
    assert body["handoff"] is None
    session = load_session(session_id)
    assert session.state == SessionState.COLLECTING_IDENTITY
    assert session.customer_id is None
    instructions = fake_model.replies_seen[-1]["extra_instructions"]
    assert HUMAN_HANDOFF_PROMPT in instructions
    assert "phone number" in instructions


def test_later_turns_of_an_unescalated_session_get_no_persona(
    client, fake_model
):
    fake_model.extraction = {"asks_about_shipment": False}

    send(client, "how long does shipping take?")

    assert fake_model.replies_seen[-1]["extra_instructions"] is None
