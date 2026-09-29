import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat_session import ChatSession, SessionState
from app.models.package import Package
from app.models.shipment import Shipment

logger = logging.getLogger(__name__)

TOOL_NAME = "lookup_shipments"

# Ollama tool definition. It deliberately takes no parameters: the customer
# always comes from the verified session, so the model is never invited to
# name one (Epic F, Section 6.3).
LOOKUP_SHIPMENTS_TOOL = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "Get the verified visitor's own shipments, each with its "
            "packages. Takes no arguments."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}

# The one result for every refusal (unverified session, unknown tool), so it
# reveals nothing about why or whether any record exists.
TOOL_UNAVAILABLE_RESULT = {"error": "Shipment information is not available."}


def is_allowed_to_look_up_shipments(session: ChatSession) -> bool:
    return (
        session.state == SessionState.VERIFIED
        and session.customer_id is not None
    )


def list_customer_shipments(db: Session, session: ChatSession) -> list[dict]:
    """The session customer's shipments with packages, as JSON-safe dicts.

    The customer id is read only from the session, never from any argument.
    """
    shipments = db.scalars(
        select(Shipment)
        .where(Shipment.customer_id == session.customer_id)
        .order_by(Shipment.last_update.desc())
    ).all()
    packages = db.scalars(
        select(Package).where(
            Package.shipment_id.in_([shipment.id for shipment in shipments])
        )
    ).all()

    return [
        {
            "tracking_number": shipment.tracking_number,
            "status": shipment.status.value,
            "carrier": shipment.carrier,
            "origin": shipment.origin,
            "destination": shipment.destination,
            "estimated_delivery": shipment.estimated_delivery.isoformat(),
            "last_update": shipment.last_update.isoformat(),
            "packages": [
                {
                    "description": package.description,
                    "weight_kg": str(package.weight_kg),
                    "declared_value": str(package.declared_value),
                }
                for package in packages
                if package.shipment_id == shipment.id
            ],
        }
        for shipment in shipments
    ]


def run_tool(
    db: Session, session: ChatSession, name: str, arguments: dict
) -> dict:
    """Run a tool the model asked for. The single enforcement point (Epic F3).

    `arguments` come from the model and are ignored on purpose: nothing it
    supplies can widen a lookup beyond the session's own customer. Only the
    tool name, session id and outcome are logged, never arguments or data.
    """
    if name != TOOL_NAME:
        # The name is model output, so it isn't logged.
        logger.warning("unknown tool refused: session %s", session.id)
        return TOOL_UNAVAILABLE_RESULT
    if not is_allowed_to_look_up_shipments(session):
        logger.warning("tool %s refused: session %s", name, session.id)
        return TOOL_UNAVAILABLE_RESULT

    logger.info("tool %s allowed: session %s", name, session.id)
    return {"shipments": list_customer_shipments(db, session)}
