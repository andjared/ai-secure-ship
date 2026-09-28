import enum
import logging
import re
from dataclasses import dataclass

from app.models.chat_session import ChatSession

logger = logging.getLogger(__name__)

# Human escalation is cosmetic theater (Epic G, Section 6.2b): there is no
# real human. It never changes the session's state or customer_id, so the
# identity gate underneath is exactly the same before and after.

HUMAN_NAME = "Melany"

# Marks the transcript turns of the scripted handoff.
ESCALATION_EVENT = "escalated_to_human"

ESCALATION_ACK_MESSAGE = (
    "Thank you for your patience, switching you to a human."
)
HUMAN_JOINED_MESSAGE = f"{HUMAN_NAME} has entered the chat"
HUMAN_READING_MESSAGE = (
    f"Hello, my name is {HUMAN_NAME}, let me just read through the chat..."
)
ALREADY_WITH_HUMAN_MESSAGE = (
    f"You're already chatting with {HUMAN_NAME}. How can I help?"
)

_HUMAN_WORDS = re.compile(
    r"\b(human|real person|live person|actual person|someone real|agent|"
    r"representative|operator)\b",
    re.IGNORECASE,
)
_REQUEST_WORDS = re.compile(
    r"\b(talk|speak|chat|connect|transfer|put me through)\b",
    re.IGNORECASE,
)


class HandoffLineKind(str, enum.Enum):
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class HandoffLine:
    kind: HandoffLineKind
    content: str


def is_asking_for_human(message: str) -> bool:
    """Whether the visitor asks to talk to a human, e.g. "I want to talk to
    a human" or "can I speak to a real person"."""
    return bool(
        _HUMAN_WORDS.search(message) and _REQUEST_WORDS.search(message)
    )


def is_escalated(transcript: list[dict]) -> bool:
    return any(turn.get("event") == ESCALATION_EVENT for turn in transcript)


def build_greeting(pending_identity: dict) -> str:
    # Only the name the visitor typed themselves is echoed back; it is never
    # looked up, so the greeting reveals nothing about customer records.
    first_name = (pending_identity.get("first_name") or "").strip()
    if first_name:
        return f"Hey {first_name}, I'm up to speed, how can I help?"
    return "Hey, I'm up to speed, how can I help?"


def start_escalation(session: ChatSession) -> list[HandoffLine]:
    """Return the scripted handoff lines to play, in order.

    A session that is already talking to the "human" gets one short line
    instead of the whole sequence again.
    """
    if is_escalated(session.transcript):
        return [
            HandoffLine(HandoffLineKind.ASSISTANT, ALREADY_WITH_HUMAN_MESSAGE)
        ]

    logger.info("escalation: started")
    return [
        HandoffLine(HandoffLineKind.ASSISTANT, ESCALATION_ACK_MESSAGE),
        HandoffLine(HandoffLineKind.SYSTEM, HUMAN_JOINED_MESSAGE),
        HandoffLine(HandoffLineKind.ASSISTANT, HUMAN_READING_MESSAGE),
        HandoffLine(
            HandoffLineKind.ASSISTANT,
            build_greeting(session.pending_identity),
        ),
    ]
