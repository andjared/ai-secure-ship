import { useState } from "react";
import type { FormEvent } from "react";
import "./ChatWindow.css";
import { useSendChatMessage } from "../../api/generated/chat";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hi! I'm the SecureShip assistant. Ask me about your shipment.",
    },
  ]);
  const [sessionId, setSessionId] = useState<string | null>(() => sessionStorage.getItem("chat_session_id"));
  const [draft, setDraft] = useState("");

  const { mutate, isPending } = useSendChatMessage();

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const text = draft?.trim();
    if (!text) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);

    mutate(
      { data: { message: text, session_id: sessionId } },
      {
        onSuccess: (response) => {
          const { reply, session_id } = response.data;
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: reply },
          ]);
          setSessionId(session_id);
          sessionStorage.setItem("chat_session_id", session_id);
        },
        onError: () => {
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: "Something went wrong — please try again.",
            },
          ]);
        },
      },
    ); 
    setDraft('')
  }

  return (
    <div className="chat-window">
      <div className="chat-window__header">SecureShip Support</div>
      <div className="chat-window__messages">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`chat-message chat-message--${message.role}`}
          >
            {message.content}
          </div>
        ))}
        {isPending && (
          <div
            className="chat-message chat-message--assistant chat-message--typing"
            role="status"
            aria-label="SecureShip assistant is typing"
          >
            <span />
            <span />
            <span />
          </div>
        )}
      </div>
      <form className="chat-window__form" onSubmit={handleSubmit}>
        <input
          className="chat-window__input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Type a message..."
          disabled={isPending}
        />
        <button
          className="chat-window__send"
          type="submit"
          disabled={isPending}
        >
          Send
        </button>
      </form>
    </div>
  );
}
