import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.llm import ollama_client
from app.models.chat_session import ChatSession

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


@router.post("/chat", operation_id="sendChatMessage")
def send_chat_message(
    request: ChatRequest, db: Session = Depends(get_db)
) -> ChatResponse:
    if request.session_id is not None:
        session = db.get(ChatSession, uuid.UUID(request.session_id))
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = ChatSession(transcript=[])
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
    reply = ollama_client.chat(request.message, history=history)
    record_turn("assistant", reply)

    db.commit()

    return ChatResponse(reply=reply, session_id=str(session.id))
