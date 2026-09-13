import os

import httpx

from app.llm.system_prompt import SYSTEM_PROMPT

OLLAMA_HOST = os.environ.get(
    "OLLAMA_HOST", "http://host.docker.internal:11434"
)


def chat(
    message: str,
    history: list[dict] | None = None,
    model: str = "qwen3:8b",
) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": message})

    response = httpx.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]
