import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SessionState(str, enum.Enum):
    ANONYMOUS = "anonymous"
    COLLECTING_IDENTITY = "collecting_identity"
    CODE_SENT = "code_sent"
    AWAITING_CODE = "awaiting_code"
    VERIFIED = "verified"
    ESCALATED_TO_HUMAN = "escalated_to_human"


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    state: Mapped[SessionState] = mapped_column(
        SAEnum(
            SessionState,
            name="session_state",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=SessionState.ANONYMOUS,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    transcript: Mapped[list] = mapped_column(JSONB, default=list)
