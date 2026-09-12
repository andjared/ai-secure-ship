from fastapi import APIRouter
from pydantic import BaseModel

from app.llm import ollama_client

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", operation_id="sendChatMessage")
def send_chat_message(request: ChatRequest) -> ChatResponse:
    reply = ollama_client.chat(request.message)
    return ChatResponse(reply=reply)
