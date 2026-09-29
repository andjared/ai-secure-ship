import json
import logging
import os
from collections.abc import Callable

import httpx

from app.llm.system_prompt import IDENTITY_EXTRACTION_PROMPT, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.environ.get(
    "OLLAMA_HOST", "http://host.docker.internal:11434"
)

# How many earlier turns the extractor sees, so a bare "Doe" can be read as
# the answer to "what's your last name?".
EXTRACTION_CONTEXT_TURNS = 4

_NULLABLE_STRING = {"type": ["string", "null"]}
IDENTITY_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "asks_about_shipment": {"type": "boolean"},
        "first_name": _NULLABLE_STRING,
        "last_name": _NULLABLE_STRING,
        "address": _NULLABLE_STRING,
        "phone_number": _NULLABLE_STRING,
    },
    "required": [
        "asks_about_shipment",
        "first_name",
        "last_name",
        "address",
        "phone_number",
    ],
}


# How many times one turn may go model -> tool -> model before giving up.
MAX_TOOL_ROUNDS = 3
TOOL_ROUNDS_EXCEEDED_MESSAGE = (
    "Sorry, I couldn't look that up right now. Please try again."
)


def _post_chat(payload: dict) -> dict:
    response = httpx.post(
        f"{OLLAMA_HOST}/api/chat",
        json={"stream": False, **payload},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["message"]


def chat(
    message: str,
    history: list[dict] | None = None,
    model: str = "qwen3:8b",
    extra_instructions: str | None = None,
    tools: list[dict] | None = None,
    run_tool: Callable[[str, dict], dict] | None = None,
) -> str:
    """Get the model's reply, running any tool calls it makes on the way.

    `tools` are offered to the model only when given, and each call is
    handed to `run_tool` (name, arguments), which decides what the model
    gets back. This module never runs a tool itself.
    """
    system_prompt = SYSTEM_PROMPT
    if extra_instructions:
        system_prompt = f"{system_prompt} {extra_instructions}"

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": message})

    payload = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools

    for _ in range(MAX_TOOL_ROUNDS + 1):
        reply = _post_chat(payload)
        tool_calls = reply.get("tool_calls") or []
        if not tool_calls or run_tool is None:
            return reply["content"]

        messages.append(reply)
        for tool_call in tool_calls:
            function = tool_call.get("function") or {}
            name = function.get("name") or ""
            arguments = function.get("arguments")
            result = run_tool(
                name, arguments if isinstance(arguments, dict) else {}
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_name": name,
                    # Unescaped, so the model reads "Čačak", not "Č...".
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    logger.warning("tool rounds exceeded")
    return TOOL_ROUNDS_EXCEEDED_MESSAGE


def extract_identity(
    message: str,
    history: list[dict] | None = None,
    model: str = "qwen3:8b",
) -> dict:
    """Ask the model to pull identity details out of the visitor's message.

    Returns whatever JSON the model produced, or an empty dict when the call
    or its output fails, so the chat carries on as plain chat. The result is
    untrusted text: callers validate it. Nothing about the message or the
    result is logged.
    """
    messages = [{"role": "system", "content": IDENTITY_EXTRACTION_PROMPT}]
    messages.extend((history or [])[-EXTRACTION_CONTEXT_TURNS:])
    messages.append({"role": "user", "content": message})

    try:
        content = _post_chat(
            {
                "model": model,
                "messages": messages,
                "format": IDENTITY_EXTRACTION_SCHEMA,
                "think": False,
                "options": {"temperature": 0},
            }
        )["content"]
        extracted = json.loads(content)
    except (httpx.HTTPError, KeyError, ValueError) as error:
        logger.warning("identity extraction failed: %s", type(error).__name__)
        return {}

    return extracted if isinstance(extracted, dict) else {}
