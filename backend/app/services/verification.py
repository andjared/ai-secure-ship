import enum
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.models.chat_session import ChatSession, SessionState

logger = logging.getLogger(__name__)

CODE_LENGTH = 6
CODE_EXPIRY_MINUTES = 10
MAX_CODE_ATTEMPTS = 3

CODE_VERIFIED_MESSAGE = "Thanks, you're verified. How can I help with your shipment?"
CODE_INCORRECT_MESSAGE = "That code isn't right. Please try again."
# The only text shown when a code can't be used any more. It must stay
# identical for every reason (expired, too many attempts, no code on file,
# session not waiting for one) so it reveals nothing about why.
CODE_RESTART_MESSAGE = (
    "That code can no longer be used. Please share your details again to get "
    "a new one."
)

# Verification codes are mock 2FA, not a real secret worth persisting: they
# live only in this process's memory for the session's lifetime and never
# reach Postgres or a log line beyond the one mock "send" below. A backend
# restart clears every outstanding code, which is fine for a mocked flow.
# This also means codes are not shared across multiple backend workers.


@dataclass
class VerificationCode:
    code: str
    expires_at: datetime
    attempts_remaining: int
    # The customer the identity check matched. It stays here, off the
    # session, until the code is verified.
    customer_id: uuid.UUID


class CodeCheckOutcome(str, enum.Enum):
    VERIFIED = "verified"
    INCORRECT = "incorrect"
    RESTART = "restart"


CODE_CHECK_MESSAGES = {
    CodeCheckOutcome.VERIFIED: CODE_VERIFIED_MESSAGE,
    CodeCheckOutcome.INCORRECT: CODE_INCORRECT_MESSAGE,
    CodeCheckOutcome.RESTART: CODE_RESTART_MESSAGE,
}

_codes: dict[uuid.UUID, VerificationCode] = {}


def generate_and_send_code(
    session_id: uuid.UUID, customer_id: uuid.UUID
) -> None:
    """Issue a fresh 6-digit code for a session, replacing any prior one.

    This is the only place a verification code is created. It logs the code
    once as a stand-in for a real SMS send (Epic C1's "mocked SMS —
    console/log output minimum") and keeps the matched customer id with it
    in memory, so no identity details ever reach this module's logs.
    """
    code = f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=CODE_EXPIRY_MINUTES
    )
    _codes[session_id] = VerificationCode(
        code=code,
        expires_at=expires_at,
        attempts_remaining=MAX_CODE_ATTEMPTS,
        customer_id=customer_id,
    )
    logger.info("mock SMS to session %s: code=%s", session_id, code)


def get_verification_code(session_id: uuid.UUID) -> VerificationCode | None:
    return _codes.get(session_id)


def is_waiting_for_code(state: SessionState) -> bool:
    """Whether the visitor should be shown the code entry modal."""
    return state in (SessionState.CODE_SENT, SessionState.AWAITING_CODE)


def _restart_verification(session: ChatSession) -> CodeCheckOutcome:
    _codes.pop(session.id, None)
    session.pending_identity = {}
    session.state = SessionState.COLLECTING_IDENTITY
    logger.info("code check: restart, session %s", session.id)
    return CodeCheckOutcome.RESTART


def check_code(session: ChatSession, submitted_code: str) -> CodeCheckOutcome:
    """Check a submitted code and move the session accordingly.

    This is the only place that sets `session.customer_id` and the only way
    into `verified`. A wrong code uses up an attempt; an expired code, the
    last failed attempt or a missing code sends the visitor back to
    `collecting_identity` to share their details again.
    """
    if not is_waiting_for_code(session.state):
        logger.info("code check: restart, session %s", session.id)
        return CodeCheckOutcome.RESTART

    entry = _codes.get(session.id)
    if entry is None or entry.expires_at <= datetime.now(timezone.utc):
        return _restart_verification(session)

    if secrets.compare_digest(submitted_code, entry.code):
        del _codes[session.id]
        session.customer_id = entry.customer_id
        session.state = SessionState.VERIFIED
        logger.info("code check: verified, session %s", session.id)
        return CodeCheckOutcome.VERIFIED

    entry.attempts_remaining -= 1
    if entry.attempts_remaining <= 0:
        return _restart_verification(session)

    session.state = SessionState.AWAITING_CODE
    logger.info("code check: incorrect, session %s", session.id)
    return CodeCheckOutcome.INCORRECT
