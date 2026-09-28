import { useState } from "react";
import type { FormEvent } from "react";
import "./ChatWindow.css";
import {
  ChatEvent,
  HandoffLineKind,
  useSendChatMessage,
} from "../../api/generated/chat";
import { CodeModal } from "../CodeModal/CodeModal";
import { useEscalationSequence } from "./useEscalationSequence";

interface Message {
  // "human" is the scripted human (Melany) after an escalation.
  role: "user" | "assistant" | "human" | "system";
  content: string;
}

export function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hi! I'm the SecureShip assistant. Ask me about your shipment.",
    },
  ]);
  const [sessionId, setSessionId] = useState<string | null>(() =>
    sessionStorage.getItem("chat_session_id"),
  );
  const [draft, setDraft] = useState("");
  const [isCodeModalOpen, setIsCodeModalOpen] = useState(false);

  const { mutate, isPending } = useSendChatMessage();
  const escalation = useEscalationSequence((line, isFromHuman) => {
    const role =
      line.kind === HandoffLineKind.assistant && isFromHuman
        ? "human"
        : line.kind;
    setMessages((prev) => [...prev, { role, content: line.content }]);
  });
  const isBusy = isPending || escalation.isPlaying;
  // Who replies: the bot, or "Melany" once the chat has been escalated.
  const replyRole = escalation.isEscalated ? "human" : "assistant";

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const text = draft?.trim();
    if (!text) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);

    mutate(
      { data: { message: text, session_id: sessionId } },
      {
        onSuccess: (response) => {
          const { reply, session_id, event, handoff } = response.data;
          if (event === ChatEvent.escalated_to_human && handoff) {
            // The reply is the handoff's first line, so it is not added twice.
            escalation.start(handoff);
          } else {
            setMessages((prev) => [
              ...prev,
              { role: replyRole, content: reply },
            ]);
          }
          setSessionId(session_id);
          sessionStorage.setItem("chat_session_id", session_id);
          if (event === ChatEvent.code_sent) {
            setIsCodeModalOpen(true);
          }
        },
        onError: () => {
          setMessages((prev) => [
            ...prev,
            {
              role: replyRole,
              content: "Something went wrong — please try again.",
            },
          ]);
        },
      },
    );
    setDraft("");
  }

  return (
    <div
      className={`chat-window${escalation.isEscalated ? " chat-window--escalated" : ""}`}
    >
      <div className="chat-window__header">
        SecureShip Support{escalation.isEscalated && " — Melany"}
      </div>
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
            className={`chat-message chat-message--${replyRole} chat-message--typing`}
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
          disabled={isBusy}
        />
        <button
          className="chat-window__send"
          type="submit"
          disabled={isBusy}
        >
          Send
        </button>
      </form>
      {sessionId && isCodeModalOpen && (
        <CodeModal
          sessionId={sessionId}
          onClose={() => setIsCodeModalOpen(false)}
          onResult={(reply) => {
            setMessages((prev) => [
              ...prev,
              { role: replyRole, content: reply },
            ]);
            setIsCodeModalOpen(false);
          }}
        />
      )}
    </div>
  );
}
