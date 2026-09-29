import os

import psycopg2
import pytest
from psycopg2 import sql
from sqlalchemy.engine import make_url

# Tests always run against their own database so they can never touch (or be
# confused by) the dev data seeded into `secureship`. This must be set before
# any `app` module is imported, since app.db.session reads it at import time.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://user:pass@localhost:5432/secureship_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL


def _ensure_test_database() -> None:
    url = make_url(TEST_DATABASE_URL)
    connection = psycopg2.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        dbname="postgres",
    )
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    sql.SQL("CREATE DATABASE {}").format(
                        sql.Identifier(url.database)
                    )
                )
    finally:
        connection.close()


_ensure_test_database()

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.llm import ollama_client  # noqa: E402
from app.main import app  # noqa: E402
from app.models import chat_session, customer, package, shipment  # noqa: E402,F401
from app.models.customer import Customer  # noqa: E402

JANE = {
    "first_name": "Jane",
    "last_name": "Doe",
    "address": "1234 Oak Ave, Austin, TX 78701",
    "phone_number": "555 123 4567",
}
JANE_MESSAGE = "Jane Doe, 1234 Oak Ave, Austin, TX 78701, 555 123 4567"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        # Tests only flush, never commit, so a rollback leaves the DB clean.
        session.rollback()
        session.close()


@pytest.fixture
def client():
    yield TestClient(app)
    # Routes commit, so clear the rows they created. Only route tests write
    # chat sessions to the test database.
    with SessionLocal() as db:
        db.execute(text("DELETE FROM chat_sessions"))
        db.commit()


@pytest.fixture
def jane_customer():
    # Routes use their own DB session, so the customer has to be committed.
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
    """Replace both Ollama calls; `extraction` is what the model 'extracts'.

    Set `tool_call` to a (name, arguments) pair to have the fake model call
    that tool once; each result lands in `tool_results`.
    """

    class FakeModel:
        extraction: dict = {}
        replies_seen: list[dict] = []
        tool_call: tuple[str, dict] | None = None
        tool_results: list[dict] = []

    def fake_extract(message, history=None, model="qwen3:8b"):
        if isinstance(FakeModel.extraction, Exception):
            raise FakeModel.extraction
        return FakeModel.extraction

    def fake_chat(
        message,
        history=None,
        model="qwen3:8b",
        extra_instructions=None,
        tools=None,
        run_tool=None,
    ):
        FakeModel.replies_seen.append(
            {"extra_instructions": extra_instructions, "tools": tools}
        )
        if FakeModel.tool_call is not None and run_tool is not None:
            FakeModel.tool_results.append(run_tool(*FakeModel.tool_call))
        return "model reply"

    FakeModel.replies_seen = []
    FakeModel.tool_call = None
    FakeModel.tool_results = []
    monkeypatch.setattr(ollama_client, "extract_identity", fake_extract)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    return FakeModel
