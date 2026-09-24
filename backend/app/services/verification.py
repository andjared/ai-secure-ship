import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.models.chat_session import SessionState

logger = logging.getLogger(__name__)

CODE_LENGTH = 6
CODE_EXPIRY_MINUTES = 10
MAX_CODE_ATTEMPTS = 3

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


_codes: dict[uuid.UUID, VerificationCode] = {}


def generate_and_send_code(session_id: uuid.UUID) -> None:
    """Issue a fresh 6-digit code for a session, replacing any prior one.

    This is the only place a verification code is created. It logs the code
    once as a stand-in for a real SMS send (Epic C1's "mocked SMS —
    console/log output minimum") and stores nothing beyond the session id and
    the code itself, so no identity details ever reach this module or its
    logs.
    """
    code = f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=CODE_EXPIRY_MINUTES
    )
    _codes[session_id] = VerificationCode(
        code=code, expires_at=expires_at, attempts_remaining=MAX_CODE_ATTEMPTS
    )
    logger.info("mock SMS to session %s: code=%s", session_id, code)


def get_verification_code(session_id: uuid.UUID) -> VerificationCode | None:
    return _codes.get(session_id)


def is_waiting_for_code(state: SessionState) -> bool:
    """Whether the visitor should be shown the code entry modal."""
    return state in (SessionState.CODE_SENT, SessionState.AWAITING_CODE)
