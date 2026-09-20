import logging
import uuid

import pytest

from app.models.customer import Customer
from app.services.identity import (
    IDENTITY_NOT_VERIFIED_MESSAGE,
    match_customer,
)

JANE = {
    "first_name": "Jane",
    "last_name": "Doe",
    "address": "1234 Oak Ave, Austin, TX 78701",
    "phone_number": "+15551234567",
}


def add_customer(db, **overrides) -> uuid.UUID:
    customer = Customer(id=uuid.uuid4(), **{**JANE, **overrides})
    db.add(customer)
    db.flush()
    return customer.id


def match(db, **overrides):
    return match_customer(db, **{**JANE, **overrides})


def test_exact_match_returns_customer_id(db):
    jane_id = add_customer(db)
    add_customer(
        db,
        first_name="John",
        last_name="Smith",
        address="9 Elm St, Denver, CO 80202",
        phone_number="+15559876543",
    )

    assert match(db) == jane_id


@pytest.mark.parametrize(
    "overrides",
    [
        {"first_name": "  JANE ", "last_name": "doe"},
        {"first_name": "Jane   ", "last_name": "\tDOE"},
        {"address": "1234 oak ave austin tx 78701"},
        {"address": "  1234  Oak Ave.,  Austin,TX   78701 "},
    ],
)
def test_case_whitespace_and_punctuation_differences_still_match(db, overrides):
    jane_id = add_customer(db)

    assert match(db, **overrides) == jane_id


@pytest.mark.parametrize(
    "phone",
    [
        "+15551234567",
        "5551234567",
        "(555) 123-4567",
        "1-555-123-4567",
        "+1 (555) 123 4567",
    ],
)
def test_phone_formats_match(db, phone):
    jane_id = add_customer(db)

    assert match(db, phone_number=phone) == jane_id


@pytest.mark.parametrize(
    "overrides",
    [
        {"first_name": "Janet"},
        {"last_name": "Roe"},
        {"address": "1235 Oak Ave, Austin, TX 78701"},
        {"phone_number": "+15551234568"},
    ],
    ids=["first_name", "last_name", "address", "phone"],
)
def test_any_single_wrong_field_fails(db, overrides):
    add_customer(db)

    assert match(db, **overrides) is None


def test_unknown_identity_fails_like_a_near_miss(db):
    add_customer(db)

    near_miss = match(db, phone_number="+15551234568")
    unknown = match(
        db,
        first_name="Nobody",
        last_name="Here",
        address="1 Nowhere Rd, Nowhere, ZZ 00000",
        phone_number="+15550000000",
    )

    assert near_miss is None
    assert unknown is None
    assert type(near_miss) is type(unknown)


def test_failure_message_is_neutral():
    message = IDENTITY_NOT_VERIFIED_MESSAGE.lower()

    for leaky in ("no customer", "not found", "no record", "exist", "phone", "address", "name"):
        assert leaky not in message


def test_same_name_customers_are_told_apart_by_phone_and_address(db):
    first_id = add_customer(db)
    second_id = add_customer(
        db,
        address="77 Pine St, Seattle, WA 98101",
        phone_number="+15557654321",
    )

    assert match(db) == first_id
    assert (
        match(
            db,
            address="77 Pine St, Seattle, WA 98101",
            phone_number="+15557654321",
        )
        == second_id
    )
    # One customer's phone with the other's address must not match anyone.
    assert match(db, address="77 Pine St, Seattle, WA 98101") is None


def test_multiple_identical_rows_fail_instead_of_guessing(db):
    add_customer(db)
    add_customer(db)

    assert match(db) is None


@pytest.mark.parametrize(
    "field", ["first_name", "last_name", "address", "phone_number"]
)
@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_blank_fields_fail(db, field, blank):
    add_customer(db)

    assert match(db, **{field: blank}) is None


@pytest.mark.parametrize("value", ["%", "_", "' OR '1'='1", "Doe%", "D_e", ".*"])
def test_wildcard_and_sql_like_input_matches_nothing(db, value):
    add_customer(db)

    assert match(db, last_name=value) is None
    assert match(db, first_name=value) is None
    assert match(db, address=value) is None
    assert match(db, phone_number=value) is None


def test_phone_without_digits_fails(db):
    add_customer(db)

    assert match(db, phone_number="call me maybe") is None


def test_submitted_values_are_never_logged(db, caplog):
    add_customer(db)
    caplog.set_level(logging.DEBUG)

    match(db)
    match(db, phone_number="+15551234568")

    logged = caplog.text
    for value in ("Jane", "Doe", "Oak Ave", "78701", "5551234567", "555123"):
        assert value not in logged
