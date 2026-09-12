import { useState } from 'react'
import type { FormEvent } from 'react'
import './ChatWindow.css'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: "Hi! I'm the SecureShip assistant. Ask me about your shipment.",
    },
  ])
  const [draft, setDraft] = useState('')

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if (!text) return

    // TODO: replace with a real POST /chat call to the backend once the
    // Ollama-backed endpoint exists (Week 1, Day 2+). Echoing for now.
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: text },
      { role: 'assistant', content: `You said: "${text}"` },
    ])
    setDraft('')
  }

  return (
    <div className="chat-window">
      <div className="chat-window__header">SecureShip Support</div>
      <div className="chat-window__messages">
        {messages.map((message, index) => (
          <div key={index} className={`chat-message chat-message--${message.role}`}>
            {message.content}
          </div>
        ))}
      </div>
      <form className="chat-window__form" onSubmit={handleSubmit}>
        <input
          className="chat-window__input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Type a message..."
        />
        <button className="chat-window__send" type="submit">
          Send
        </button>
      </form>
    </div>
  )
}
