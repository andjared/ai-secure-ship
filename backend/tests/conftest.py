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

from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.models import chat_session, customer, package, shipment  # noqa: E402,F401


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
