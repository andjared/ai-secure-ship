import enum
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.llm import ollama_client
from app.llm.system_prompt import identity_collection_prompt
from app.models.chat_session import ChatSession, SessionState
from app.services import identity, verification

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatEvent(str, enum.Enum):
    """Something the client should react to after this turn."""

    CODE_SENT = "code_sent"


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    event: ChatEvent | None = None


@router.post("/chat", operation_id="sendChatMessage")
def send_chat_message(
    request: ChatRequest, db: Session = Depends(get_db)
) -> ChatResponse:
    if request.session_id is not None:
        session = db.get(ChatSession, uuid.UUID(request.session_id))
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        # Column defaults only apply at INSERT, but the state is read below.
        session = ChatSession(
            transcript=[],
            state=SessionState.ANONYMOUS,
            pending_identity={},
        )
        db.add(session)

    history = [
        {"role": turn["role"], "content": turn["content"]}
        for turn in session.transcript
    ]

    def record_turn(role: str, content: str) -> None:
        session.transcript = [
            *session.transcript,
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        ]

    record_turn("user", request.message)

    extra_instructions = None
    reply = None
    if session.state in identity.COLLECTING_STATES:
        extracted = ollama_client.extract_identity(
            request.message, history=history
        )
        identity.collect_identity(session, extracted, request.message)
        if session.state == SessionState.COLLECTING_IDENTITY:
            missing = identity.list_missing_identity_labels(
                session.pending_identity
            )
            if missing:
                extra_instructions = identity_collection_prompt(missing)
            elif identity.check_collected_identity(db, session):
                # A new session's id is only assigned on flush/INSERT.
                db.flush()
                verification.generate_and_send_code(session.id)
                reply = identity.IDENTITY_COLLECTED_MESSAGE
            else:
                reply = identity.IDENTITY_NOT_VERIFIED_MESSAGE

    if reply is None:
        reply = ollama_client.chat(
            request.message,
            history=history,
            extra_instructions=extra_instructions,
        )
    record_turn("assistant", reply)

    db.commit()

    event = (
        ChatEvent.CODE_SENT
        if verification.is_waiting_for_code(session.state)
        else None
    )
    return ChatResponse(reply=reply, session_id=str(session.id), event=event)
