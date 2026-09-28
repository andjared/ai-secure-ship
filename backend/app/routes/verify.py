import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.chat_session import ChatSession
from app.services import verification
from app.services.verification import CodeCheckOutcome

router = APIRouter()


class VerifyCodeRequest(BaseModel):
    session_id: str
    code: str = Field(
        pattern=rf"^[0-9]{{{verification.CODE_LENGTH}}}$"
    )


class VerifyCodeResponse(BaseModel):
    outcome: CodeCheckOutcome
    reply: str
    attempts_remaining: int | None = None


@router.post("/verify-code", operation_id="verifyCode")
def verify_code(
    request: VerifyCodeRequest, db: Session = Depends(get_db)
) -> VerifyCodeResponse:
    session = db.get(ChatSession, uuid.UUID(request.session_id))
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    outcome = verification.check_code(session, request.code)
    reply = verification.CODE_CHECK_MESSAGES[outcome]

    # Only the reply is recorded; the submitted code never reaches the
    # transcript.
    session.transcript = [
        *session.transcript,
        {
            "role": "assistant",
            "content": reply,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    ]
    db.commit()

    entry = verification.get_verification_code(session.id)
    attempts_remaining = (
        entry.attempts_remaining
        if outcome == CodeCheckOutcome.INCORRECT and entry is not None
        else None
    )
    return VerifyCodeResponse(
        outcome=outcome, reply=reply, attempts_remaining=attempts_remaining
    )
