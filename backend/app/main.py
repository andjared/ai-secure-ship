import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.session import Base, engine
from app.models import chat_session, customer, package, shipment  # noqa: F401
from app.routes import chat

# Without this, the root logger defaults to WARNING and the mock 2FA
# "console/log output" (Epic C1) never reaches the terminal.
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="SecureShip API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
