import logging
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.chat_session import SessionState
from app.services import verification


@pytest.fixture(autouse=True)
def _clear_codes(monkeypatch):
    monkeypatch.setattr(verification, "_codes", {})


def test_generated_code_is_six_digits(monkeypatch):
    session_id = uuid.uuid4()
    monkeypatch.setattr(verification.secrets, "randbelow", lambda _: 5)

    verification.generate_and_send_code(session_id)

    entry = verification.get_verification_code(session_id)
    assert entry.code == "000005"


def test_code_expires_in_the_configured_window():
    session_id = uuid.uuid4()
    before = datetime.now(timezone.utc)

    verification.generate_and_send_code(session_id)

    entry = verification.get_verification_code(session_id)
    expected = before + timedelta(minutes=verification.CODE_EXPIRY_MINUTES)
    assert expected - timedelta(seconds=5) <= entry.expires_at <= expected + timedelta(
        seconds=5
    )


def test_attempts_remaining_starts_at_the_max():
    session_id = uuid.uuid4()

    verification.generate_and_send_code(session_id)

    entry = verification.get_verification_code(session_id)
    assert entry.attempts_remaining == verification.MAX_CODE_ATTEMPTS


def test_regenerating_replaces_the_previous_code():
    session_id = uuid.uuid4()

    verification.generate_and_send_code(session_id)
    first = verification.get_verification_code(session_id)
    verification.generate_and_send_code(session_id)
    second = verification.get_verification_code(session_id)

    assert first.code != second.code or first.expires_at != second.expires_at
    assert second.attempts_remaining == verification.MAX_CODE_ATTEMPTS


def test_unknown_session_has_no_code():
    assert verification.get_verification_code(uuid.uuid4()) is None


def test_only_the_mock_send_line_is_logged(caplog):
    session_id = uuid.uuid4()

    with caplog.at_level(logging.DEBUG):
        verification.generate_and_send_code(session_id)

    records = [r for r in caplog.records if r.name == verification.__name__]
    assert len(records) == 1
    message = records[0].getMessage()
    assert str(session_id) in message
    assert verification.get_verification_code(session_id).code in message


@pytest.mark.parametrize("state", list(SessionState))
def test_only_code_states_are_waiting_for_a_code(state):
    expected = state in (SessionState.CODE_SENT, SessionState.AWAITING_CODE)
    assert verification.is_waiting_for_code(state) is expected
