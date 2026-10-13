import { Fragment, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import "./ChatWindow.css";
import {
  ChatEvent,
  HandoffLineKind,
  useSendChatMessage,
  type ShipmentInfo,
} from "../../api/generated/chat";
import { CodeModal } from "../CodeModal/CodeModal";
import { useEscalationSequence } from "./useEscalationSequence";
import { ShipmentCard } from "../ShipmentCard/ShipmentCard";

interface Message {
  // "human" is the scripted human (Melany) after an escalation.
  role: "user" | "assistant" | "human" | "system";
  content: string;
  shipments?: ShipmentInfo[] | null;
}

// The model is told to reply in plain text but sometimes still wraps words in
// asterisks; drop the markers so they are never shown.
function removeEmphasisMarkers(text: string) {
  return text.replace(/\*{1,2}([^*\n]+)\*{1,2}/g, "$1");
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

  const messageList = useRef<HTMLDivElement>(null);
  const messageInput = useRef<HTMLInputElement>(null);

  // Keep the newest message (or the typing dots) in view.
  useEffect(() => {
    const list = messageList.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [messages.length, isPending]);

  // The input is disabled while a reply is on its way, which drops focus.
  useEffect(() => {
    if (!isBusy && !isCodeModalOpen) messageInput.current?.focus();
  }, [isBusy, isCodeModalOpen]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const text = draft?.trim();
    if (!text) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);

    mutate(
      { data: { message: text, session_id: sessionId } },
      {
        onSuccess: (response) => {
          const { reply, session_id, event, handoff, shipments } =
            response.data;
          if (event === ChatEvent.escalated_to_human && handoff) {
            // The reply is the handoff's first line, so it is not added twice.
            escalation.start(handoff);
          } else {
            setMessages((prev) => [
              ...prev,
              { role: replyRole, content: reply, shipments },
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
      <header className="chat-window__header">
        <span className="chat-window__title">SecureShip Support</span>
        <span className="chat-window__status">
          {escalation.isEscalated ? "Melany · support agent" : "AI assistant"}
        </span>
      </header>
      <div className="chat-window__messages" ref={messageList}>
        {messages.map((message, index) => (
          <Fragment key={index}>
            <div className={`chat-message chat-message--${message.role}`}>
              {message.role === "user"
                ? message.content
                : removeEmphasisMarkers(message.content)}
            </div>
            {message.shipments && message.shipments.length > 0 && (
              <div className="chat-window__shipments">
                {message.shipments.map((shipment) => (
                  <ShipmentCard
                    key={shipment.tracking_number}
                    shipment={shipment}
                  />
                ))}
              </div>
            )}
          </Fragment>
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
          ref={messageInput}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Type a message..."
          disabled={isBusy}
        />
        <button className="chat-window__send" type="submit" disabled={isBusy}>
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
