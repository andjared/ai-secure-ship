import enum
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.llm import ollama_client
from app.llm.system_prompt import (
    HUMAN_HANDOFF_PROMPT,
    VERIFIED_SHIPMENTS_PROMPT,
    identity_collection_prompt,
)
from app.models.chat_session import ChatSession, SessionState
from app.services import escalation, identity, verification
from app.services.escalation import HandoffLine
from app.tools import lookup_shipments

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatEvent(str, enum.Enum):
    """Something the client should react to after this turn."""

    CODE_SENT = "code_sent"
    ESCALATED_TO_HUMAN = "escalated_to_human"


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    event: ChatEvent | None = None
    # The scripted human handoff, in order; only set with ESCALATED_TO_HUMAN.
    handoff: list[HandoffLine] | None = None


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

    def record_turn(
        role: str,
        content: str,
        event: str | None = None,
        tool_calls: list[str] | None = None,
    ) -> None:
        turn = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if event is not None:
            turn["event"] = event
        if tool_calls:
            turn["tool_calls"] = tool_calls
        session.transcript = [*session.transcript, turn]

    tools_called: list[str] = []

    def run_tool(name: str, arguments: dict) -> dict:
        tools_called.append(name)
        return lookup_shipments.run_tool(db, session, name, arguments)

    record_turn("user", request.message)

    instructions = []
    reply = None
    handoff = None
    if escalation.is_asking_for_human(request.message):
        handoff = escalation.start_escalation(session)
        reply = handoff[0].content
    elif session.state in identity.COLLECTING_STATES:
        extracted = ollama_client.extract_identity(
            request.message, history=history
        )
        identity.collect_identity(session, extracted, request.message)
        if session.state == SessionState.COLLECTING_IDENTITY:
            missing = identity.list_missing_identity_labels(
                session.pending_identity
            )
            if missing:
                instructions.append(identity_collection_prompt(missing))
            else:
                customer_id = identity.check_collected_identity(db, session)
                if customer_id is not None:
                    # A new session's id is only assigned on flush/INSERT.
                    db.flush()
                    verification.generate_and_send_code(
                        session.id, customer_id
                    )
                    reply = identity.IDENTITY_COLLECTED_MESSAGE
                else:
                    reply = identity.IDENTITY_NOT_VERIFIED_MESSAGE

    if reply is None:
        if escalation.is_escalated(session.transcript):
            instructions.append(HUMAN_HANDOFF_PROMPT)
        # Unverified sessions are never even offered the tool; run_tool
        # checks again regardless.
        tools = None
        if lookup_shipments.is_allowed_to_look_up_shipments(session):
            instructions.append(VERIFIED_SHIPMENTS_PROMPT)
            tools = [lookup_shipments.LOOKUP_SHIPMENTS_TOOL]
        reply = ollama_client.chat(
            request.message,
            history=history,
            extra_instructions=" ".join(instructions) or None,
            tools=tools,
            run_tool=run_tool,
        )

    if handoff is not None:
        for line in handoff:
            record_turn(
                line.kind.value, line.content, event=escalation.ESCALATION_EVENT
            )
    else:
        record_turn("assistant", reply, tool_calls=tools_called)

    db.commit()

    if handoff is not None:
        event = ChatEvent.ESCALATED_TO_HUMAN
    elif verification.is_waiting_for_code(session.state):
        event = ChatEvent.CODE_SENT
    else:
        event = None
    return ChatResponse(
        reply=reply, session_id=str(session.id), event=event, handoff=handoff
    )
