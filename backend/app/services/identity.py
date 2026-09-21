import logging
import re
import unicodedata
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chat_session import ChatSession, SessionState
from app.models.customer import Customer

logger = logging.getLogger(__name__)

# Order matters: it is the order the assistant asks for missing details.
IDENTITY_FIELD_LABELS = {
    "first_name": "first name",
    "last_name": "last name",
    "address": "address",
    "phone_number": "phone number",
}
MAX_IDENTITY_FIELD_LENGTH = 200

# Sessions where the backend still collects identity details.
COLLECTING_STATES = (SessionState.ANONYMOUS, SessionState.COLLECTING_IDENTITY)

# Shown once all four details are collected, so the model never gets to claim
# a verification that hasn't happened.
IDENTITY_COLLECTED_MESSAGE = "Thanks, let me check those details."

# The only text a caller may show a visitor when matching fails. It must stay
# identical for every failure (unknown person, wrong field, duplicate rows) so
# it can't be used to probe which customers exist (Epic B3).
IDENTITY_NOT_VERIFIED_MESSAGE = (
    "Sorry, we couldn't verify those details. Please double-check them and "
    "try again."
)

_WHITESPACE = re.compile(r"\s+")
_NON_DIGITS = re.compile(r"[^0-9]")


def _normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    return _WHITESPACE.sub(" ", text).strip()


def _normalize_address(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    text = "".join(
        " " if unicodedata.category(char).startswith("P") else char
        for char in text
    )
    return _WHITESPACE.sub(" ", text).strip()


def _normalize_phone(value: str) -> str:
    digits = _NON_DIGITS.sub("", value)
    # A leading US country code is optional: +1 555 123 4567 == 555 123 4567.
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    return digits


def match_customer(
    db: Session,
    *,
    first_name: str,
    last_name: str,
    address: str,
    phone_number: str,
) -> uuid.UUID | None:
    """Return the id of the one customer matching all four fields, else None.

    The result intentionally carries no failure reason: callers can't leak
    which field was wrong or whether a similar record exists. Callers show
    IDENTITY_NOT_VERIFIED_MESSAGE on None.
    """
    wanted_first = _normalize_name(first_name)
    wanted_last = _normalize_name(last_name)
    wanted_address = _normalize_address(address)
    wanted_phone = _normalize_phone(phone_number)

    if not (wanted_first and wanted_last and wanted_address and wanted_phone):
        logger.info("identity match: miss")
        return None

    # Narrow by phone in SQL using digits only, which is exactly what the
    # Python normalizer keeps. Every other comparison uses the shared Python
    # helpers so there is one definition of "equal".
    candidate_digits = {wanted_phone, f"1{wanted_phone}"}
    stored_digits = func.regexp_replace(
        Customer.phone_number, "[^0-9]", "", "g"
    )
    candidates = db.scalars(
        select(Customer).where(stored_digits.in_(candidate_digits))
    ).all()

    matches = [
        customer.id
        for customer in candidates
        if _normalize_phone(customer.phone_number) == wanted_phone
        and _normalize_name(customer.first_name) == wanted_first
        and _normalize_name(customer.last_name) == wanted_last
        and _normalize_address(customer.address) == wanted_address
    ]

    # Two identical rows would make any pick a guess; treat as a miss.
    if len(matches) != 1:
        logger.info("identity match: miss")
        return None

    logger.info("identity match: hit")
    return matches[0]


def _appears_in_message(field: str, value: str, message: str) -> bool:
    if field == "phone_number":
        wanted = _normalize_phone(value)
        return bool(wanted) and wanted in _NON_DIGITS.sub("", message)

    normalize = _normalize_address if field == "address" else _normalize_name
    wanted = normalize(value)
    return bool(wanted) and wanted in normalize(message)


def clean_extracted_identity(extracted: dict, message: str) -> dict[str, str]:
    """Keep only the identity details the visitor really typed.

    The extractor's output is untrusted model text. A value survives only if
    it is a reasonably short string that visibly appears in `message`, so an
    invented detail never lands on the session.
    """
    cleaned = {}
    for field in IDENTITY_FIELD_LABELS:
        value = extracted.get(field)
        if not isinstance(value, str):
            continue
        value = value.strip()
        if len(value) > MAX_IDENTITY_FIELD_LENGTH:
            continue
        if _appears_in_message(field, value, message):
            cleaned[field] = value
    return cleaned


def list_missing_identity_labels(pending_identity: dict) -> list[str]:
    return [
        label
        for field, label in IDENTITY_FIELD_LABELS.items()
        if not pending_identity.get(field)
    ]


def collect_identity(
    session: ChatSession,
    extracted: dict,
    message: str,
) -> None:
    """Apply one turn of extracted details to a session still collecting them.
    This is the only place that moves a session into `collecting_identity`;
    the model only supplies text. Sessions in any other state are untouched.
    """
    if session.state not in COLLECTING_STATES:
        return

    if session.state == SessionState.ANONYMOUS:
        if extracted.get("asks_about_shipment") is not True:
            return
        session.state = SessionState.COLLECTING_IDENTITY
        logger.info("identity collection: started")

    # A newer value replaces an older one, so the visitor can correct a detail.
    session.pending_identity = {
        **session.pending_identity,
        **clean_extracted_identity(extracted, message),
    }
