from app.models.chat_session import ChatSession, SessionState
from app.services.identity import (
    MAX_IDENTITY_FIELD_LENGTH,
    clean_extracted_identity,
    collect_identity,
    list_missing_identity_labels,
)

ALL_FIELDS_MESSAGE = (
    "I'm Jane Doe, 1234 Oak Ave, Austin, TX 78701, phone +1 555 123 4567"
)
ALL_FIELDS = {
    "first_name": "Jane",
    "last_name": "Doe",
    "address": "1234 Oak Ave, Austin, TX 78701",
    "phone_number": "+1 555 123 4567",
}


def new_session(state=SessionState.ANONYMOUS, pending=None) -> ChatSession:
    return ChatSession(transcript=[], state=state, pending_identity=pending or {})


def test_shipment_question_starts_collecting():
    session = new_session()

    collect_identity(session, {"asks_about_shipment": True}, "where's my package?")

    assert session.state == SessionState.COLLECTING_IDENTITY
    assert session.pending_identity == {}


def test_general_question_stays_anonymous_and_stores_nothing():
    session = new_session()

    collect_identity(
        session,
        {"asks_about_shipment": False, "first_name": "Jane"},
        "hi, I'm Jane",
    )

    assert session.state == SessionState.ANONYMOUS
    assert session.pending_identity == {}


def test_string_true_does_not_count_as_shipment_question():
    session = new_session()

    collect_identity(session, {"asks_about_shipment": "true"}, "hello")

    assert session.state == SessionState.ANONYMOUS


def test_details_given_with_the_shipment_question_are_kept():
    session = new_session()

    collect_identity(
        session,
        {"asks_about_shipment": True, "first_name": "Jane", "last_name": "Doe"},
        "I'm Jane Doe, where is my package?",
    )

    assert session.state == SessionState.COLLECTING_IDENTITY
    assert session.pending_identity == {"first_name": "Jane", "last_name": "Doe"}


def test_details_accumulate_across_turns_in_any_order():
    session = new_session(SessionState.COLLECTING_IDENTITY)

    collect_identity(session, {"phone_number": "555 123 4567"}, "555 123 4567")
    collect_identity(session, {"last_name": "Doe"}, "Doe")
    collect_identity(
        session,
        {"first_name": "Jane", "address": "1234 Oak Ave"},
        "Jane, 1234 Oak Ave",
    )

    assert session.pending_identity == {
        "phone_number": "555 123 4567",
        "last_name": "Doe",
        "first_name": "Jane",
        "address": "1234 Oak Ave",
    }
    assert session.state == SessionState.COLLECTING_IDENTITY
    assert list_missing_identity_labels(session.pending_identity) == []


def test_a_newer_value_replaces_an_older_one():
    session = new_session(
        SessionState.COLLECTING_IDENTITY, {"last_name": "Dow"}
    )

    collect_identity(session, {"last_name": "Doe"}, "sorry, it's Doe")

    assert session.pending_identity == {"last_name": "Doe"}


def test_missing_labels_follow_asking_order():
    assert list_missing_identity_labels({}) == [
        "first name",
        "last name",
        "address",
        "phone number",
    ]
    assert list_missing_identity_labels(
        {"first_name": "Jane", "address": "1 Main St"}
    ) == ["last name", "phone number"]


def test_other_states_are_untouched():
    for state in (
        SessionState.CODE_SENT,
        SessionState.AWAITING_CODE,
        SessionState.VERIFIED,
        SessionState.ESCALATED_TO_HUMAN,
    ):
        session = new_session(state)

        collect_identity(
            session,
            {"asks_about_shipment": True, "first_name": "Jane"},
            "Jane, where is my package?",
        )

        assert session.state == state
        assert session.pending_identity == {}


def test_all_four_fields_survive_when_typed_by_the_visitor():
    assert clean_extracted_identity(ALL_FIELDS, ALL_FIELDS_MESSAGE) == ALL_FIELDS


def test_values_the_visitor_never_typed_are_dropped():
    extracted = {**ALL_FIELDS, "last_name": "Smith", "phone_number": "555 000 1111"}

    cleaned = clean_extracted_identity(extracted, ALL_FIELDS_MESSAGE)

    assert "last_name" not in cleaned
    assert "phone_number" not in cleaned
    assert cleaned["first_name"] == "Jane"


def test_grounding_ignores_case_spacing_and_phone_formatting():
    cleaned = clean_extracted_identity(
        {"first_name": "JANE", "phone_number": "5551234567"},
        "jane   here, call me on (555) 123-4567",
    )

    assert cleaned == {"first_name": "JANE", "phone_number": "5551234567"}


def test_non_string_empty_and_overlong_values_are_dropped():
    long_name = "a" * (MAX_IDENTITY_FIELD_LENGTH + 1)

    cleaned = clean_extracted_identity(
        {
            "first_name": 42,
            "last_name": "   ",
            "address": long_name,
            "phone_number": None,
        },
        f"42 {long_name}",
    )

    assert cleaned == {}


def test_values_are_trimmed():
    assert clean_extracted_identity({"first_name": "  Jane "}, "Jane") == {
        "first_name": "Jane"
    }
