import logging
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal
from app.models.chat_session import ChatSession, SessionState
from app.services import verification
from app.services.verification import CodeCheckOutcome
from tests.conftest import JANE, JANE_MESSAGE


@pytest.fixture(autouse=True)
def _clear_codes(monkeypatch):
    monkeypatch.setattr(verification, "_codes", {})


def wrong_code_for(code: str) -> str:
    return f"{(int(code) + 1) % 10**verification.CODE_LENGTH:0{verification.CODE_LENGTH}d}"


def add_session(db, state=SessionState.CODE_SENT) -> ChatSession:
    session = ChatSession(state=state, pending_identity=dict(JANE))
    db.add(session)
    db.flush()
    return session


def issue_code(session_id, customer_id=None) -> str:
    verification.generate_and_send_code(session_id, customer_id or uuid.uuid4())
    return verification.get_verification_code(session_id).code


# --- check_code ---------------------------------------------------------------


def test_correct_code_verifies_and_sets_the_matched_customer(db):
    session = add_session(db)
    customer_id = uuid.uuid4()
    code = issue_code(session.id, customer_id)

    outcome = verification.check_code(session, code)

    assert outcome == CodeCheckOutcome.VERIFIED
    assert session.state == SessionState.VERIFIED
    assert session.customer_id == customer_id
    assert verification.get_verification_code(session.id) is None


def test_wrong_code_uses_an_attempt(db):
    session = add_session(db)
    code = issue_code(session.id)

    outcome = verification.check_code(session, wrong_code_for(code))

    assert outcome == CodeCheckOutcome.INCORRECT
    assert session.state == SessionState.AWAITING_CODE
    assert session.customer_id is None
    entry = verification.get_verification_code(session.id)
    assert entry.attempts_remaining == verification.MAX_CODE_ATTEMPTS - 1


def assert_restarted(session):
    assert session.state == SessionState.COLLECTING_IDENTITY
    assert session.pending_identity == {}
    assert session.customer_id is None
    assert verification.get_verification_code(session.id) is None


def test_last_wrong_code_restarts_verification(db):
    session = add_session(db)
    code = issue_code(session.id)

    outcomes = [
        verification.check_code(session, wrong_code_for(code))
        for _ in range(verification.MAX_CODE_ATTEMPTS)
    ]

    assert outcomes[-1] == CodeCheckOutcome.RESTART
    assert set(outcomes[:-1]) == {CodeCheckOutcome.INCORRECT}
    assert_restarted(session)


def test_expired_code_restarts_even_when_correct(db):
    session = add_session(db)
    code = issue_code(session.id)
    verification.get_verification_code(session.id).expires_at = datetime.now(
        timezone.utc
    ) - timedelta(seconds=1)

    outcome = verification.check_code(session, code)

    assert outcome == CodeCheckOutcome.RESTART
    assert_restarted(session)


def test_code_cannot_be_used_twice(db):
    session = add_session(db)
    code = issue_code(session.id)
    assert verification.check_code(session, code) == CodeCheckOutcome.VERIFIED

    session.state = SessionState.AWAITING_CODE
    outcome = verification.check_code(session, code)

    assert outcome == CodeCheckOutcome.RESTART
    assert session.state == SessionState.COLLECTING_IDENTITY


def test_no_code_on_file_restarts(db):
    session = add_session(db)

    outcome = verification.check_code(session, "123456")

    assert outcome == CodeCheckOutcome.RESTART
    assert_restarted(session)


@pytest.mark.parametrize(
    "state",
    [
        SessionState.ANONYMOUS,
        SessionState.COLLECTING_IDENTITY,
        SessionState.VERIFIED,
        SessionState.ESCALATED_TO_HUMAN,
    ],
)
def test_session_not_waiting_for_a_code_is_left_unchanged(db, state):
    session = add_session(db, state)
    code = issue_code(session.id)

    outcome = verification.check_code(session, code)

    assert outcome == CodeCheckOutcome.RESTART
    assert session.state == state
    assert session.customer_id is None


def test_code_checks_log_neither_the_code_nor_the_customer(db, caplog):
    session = add_session(db)
    customer_id = uuid.uuid4()
    code = issue_code(session.id, customer_id)
    # Drop the mock SMS line from issuing the code; only the checks count.
    caplog.clear()

    with caplog.at_level(logging.DEBUG):
        verification.check_code(session, wrong_code_for(code))
        verification.check_code(session, code)

    assert code not in caplog.text
    assert wrong_code_for(code) not in caplog.text
    assert str(customer_id) not in caplog.text
    assert "code check: incorrect" in caplog.text
    assert "code check: verified" in caplog.text


# --- POST /verify-code --------------------------------------------------------


def create_session(state=SessionState.CODE_SENT) -> uuid.UUID:
    with SessionLocal() as db:
        session = ChatSession(state=state)
        db.add(session)
        db.commit()
        return session.id


def load_session(session_id) -> ChatSession:
    with SessionLocal() as db:
        return db.get(ChatSession, session_id)


def submit(client, session_id, code):
    return client.post(
        "/verify-code", json={"session_id": str(session_id), "code": code}
    )


def test_route_verifies_a_correct_code(client):
    session_id = create_session()
    customer_id = uuid.uuid4()
    code = issue_code(session_id, customer_id)

    response = submit(client, session_id, code)

    assert response.status_code == 200
    assert response.json() == {
        "outcome": "verified",
        "reply": verification.CODE_VERIFIED_MESSAGE,
        "attempts_remaining": None,
    }
    session = load_session(session_id)
    assert session.state == SessionState.VERIFIED
    assert session.customer_id == customer_id


def test_route_reports_attempts_left_after_a_wrong_code(client):
    session_id = create_session()
    code = issue_code(session_id)

    body = submit(client, session_id, wrong_code_for(code)).json()

    assert body["outcome"] == "incorrect"
    assert body["reply"] == verification.CODE_INCORRECT_MESSAGE
    assert body["attempts_remaining"] == verification.MAX_CODE_ATTEMPTS - 1
    assert load_session(session_id).state == SessionState.AWAITING_CODE


def test_route_restarts_after_the_last_wrong_code(client):
    session_id = create_session()
    code = issue_code(session_id)

    for _ in range(verification.MAX_CODE_ATTEMPTS):
        body = submit(client, session_id, wrong_code_for(code)).json()

    assert body["outcome"] == "restart"
    assert body["attempts_remaining"] is None
    session = load_session(session_id)
    assert session.state == SessionState.COLLECTING_IDENTITY
    assert session.customer_id is None


def test_every_restart_reason_gets_the_same_reply(client):
    expired_id = create_session()
    issue_code(expired_id)
    verification.get_verification_code(expired_id).expires_at = datetime.now(
        timezone.utc
    ) - timedelta(seconds=1)

    exhausted_id = create_session()
    exhausted_code = issue_code(exhausted_id)
    for _ in range(verification.MAX_CODE_ATTEMPTS - 1):
        submit(client, exhausted_id, wrong_code_for(exhausted_code))

    missing_id = create_session()
    wrong_state_id = create_session(SessionState.ANONYMOUS)

    replies = {
        submit(client, expired_id, "123456").json()["reply"],
        submit(client, exhausted_id, wrong_code_for(exhausted_code)).json()["reply"],
        submit(client, missing_id, "123456").json()["reply"],
        submit(client, wrong_state_id, "123456").json()["reply"],
    }

    assert replies == {verification.CODE_RESTART_MESSAGE}


def test_submitted_codes_never_reach_the_transcript(client):
    session_id = create_session()
    code = issue_code(session_id)

    submit(client, session_id, wrong_code_for(code))
    submit(client, session_id, code)

    transcript = load_session(session_id).transcript
    assert [turn["role"] for turn in transcript] == ["assistant", "assistant"]
    assert [turn["content"] for turn in transcript] == [
        verification.CODE_INCORRECT_MESSAGE,
        verification.CODE_VERIFIED_MESSAGE,
    ]
    assert code not in str(transcript)
    assert wrong_code_for(code) not in str(transcript)


def test_unknown_session_returns_404(client):
    response = submit(client, uuid.uuid4(), "123456")

    assert response.status_code == 404


@pytest.mark.parametrize("bad_code", ["12345", "1234567", "abcdef", "12 345"])
def test_malformed_code_is_rejected_without_using_an_attempt(client, bad_code):
    session_id = create_session()
    issue_code(session_id)

    response = submit(client, session_id, bad_code)

    assert response.status_code == 422
    entry = verification.get_verification_code(session_id)
    assert entry.attempts_remaining == verification.MAX_CODE_ATTEMPTS
    assert load_session(session_id).state == SessionState.CODE_SENT


def test_chat_then_code_verifies_the_matched_customer(
    client, fake_model, jane_customer
):
    fake_model.extraction = {"asks_about_shipment": True, **JANE}
    chat = client.post("/chat", json={"message": JANE_MESSAGE, "session_id": None})
    session_id = uuid.UUID(chat.json()["session_id"])
    code = verification.get_verification_code(session_id).code

    body = submit(client, session_id, code).json()

    assert body["outcome"] == "verified"
    session = load_session(session_id)
    assert session.state == SessionState.VERIFIED
    assert session.customer_id == jane_customer
