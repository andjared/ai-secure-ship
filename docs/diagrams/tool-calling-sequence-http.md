# Tool-Calling Sequence — HTTP (the gating enforcement point)

As implemented (`backend/app/routes/chat.py`, `routes/verify.py`, `services/identity.py`, `services/verification.py`, `llm/ollama_client.py`, `tools/lookup_shipments.py`). Plain HTTP request/response is the only transport in this build.

The model has exactly one tool, `lookup_shipments`, and only a verified session is offered it. Identity collection, matching and code checking are backend steps, not tools the model can call.

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant BE as Backend routes
    participant Svc as Services (identity, verification)
    participant LLM as Ollama (qwen3 8b)
    participant Tools as Tool layer (run_tool)
    participant DB as Postgres

    Note over User,DB: 1. Collecting identity (state anonymous, then collecting_identity)
    User->>FE: "Where's my package?"
    FE->>BE: POST /chat {message, session_id}
    BE->>DB: load or create chat session
    BE->>LLM: extract_identity (structured output, recent turns)
    LLM-->>BE: asks_about_shipment + proposed details
    BE->>Svc: collect_identity
    Note over Svc: Keeps a detail only if it appears<br/>in the visitor's message.<br/>Sets state collecting_identity.
    BE->>LLM: chat, with the list of missing details
    LLM-->>BE: reply asking for them
    BE->>DB: save transcript, state, pending_identity
    BE-->>FE: {reply, session_id}
    FE->>User: shows reply

    Note over User,DB: 2. All four details present, match and send code
    User->>FE: gives the remaining details
    FE->>BE: POST /chat {message, session_id}
    BE->>LLM: extract_identity
    LLM-->>BE: proposed details
    BE->>Svc: collect_identity, then check_collected_identity
    Svc->>DB: match_customer (first name, last name, address, phone)
    alt exactly one customer matches
        DB-->>Svc: customer id
        Svc->>Svc: state code_sent, keep code + customer id in memory, log mock SMS
        BE->>DB: save transcript and state (customer_id still empty)
        BE-->>FE: {fixed reply, event code_sent}
        FE->>User: opens the 6-digit code modal
    else no match
        Svc->>Svc: clear pending_identity, state stays collecting_identity
        BE-->>FE: {neutral "couldn't verify" reply}
    end

    Note over User,DB: 3. Code check
    User->>FE: enters code
    FE->>BE: POST /verify-code {session_id, code}
    BE->>Svc: check_code
    alt correct, not expired
        Svc->>Svc: set customer_id and state verified, drop the code
        BE->>DB: save session and reply
        BE-->>FE: {outcome verified, reply}
        FE->>User: closes modal, shows reply
    else wrong, attempts left
        Svc->>Svc: one attempt used, state awaiting_code
        BE-->>FE: {outcome incorrect, reply, attempts_remaining}
        FE->>User: modal stays open with the error
    else expired, last attempt failed or no code
        Svc->>Svc: drop code, clear details, state collecting_identity
        BE-->>FE: {outcome restart, neutral reply}
        FE->>User: closes modal, shows reply
    end

    Note over User,DB: 4. Verified shipment question
    User->>FE: "What's the status of my shipment?"
    FE->>BE: POST /chat {message, session_id}
    BE->>DB: load session (state verified, customer_id set)
    BE->>LLM: chat + lookup_shipments tool definition (no parameters)
    LLM-->>BE: tool_call lookup_shipments
    BE->>Tools: run_tool(session, name, arguments)
    Note over Tools: Enforcement point.<br/>Arguments from the model are ignored.<br/>Refuses unless the session is verified<br/>and has a customer_id.<br/>The customer comes only from the session.
    Tools->>DB: shipments where customer_id = session.customer_id
    Tools->>DB: packages of those shipments
    DB-->>Tools: rows
    Tools-->>BE: {shipments}
    BE->>LLM: tool result
    LLM-->>BE: natural-language answer
    BE->>DB: save transcript (tool name recorded on the turn)
    BE-->>FE: {reply, shipments}
    FE->>User: reply plus shipment cards
```

Notes:
- The tool definition has no parameters, so there is no customer argument for the model or the visitor to supply. `run_tool` re-checks the session on every call even though unverified sessions are never offered the tool.
- Every refusal (unverified session, unknown tool name) returns the same `TOOL_UNAVAILABLE_RESULT`, and no shipment data reaches the client for that turn.
- The model may go model → tool → model at most `MAX_TOOL_ROUNDS` (3) times per turn; after that the visitor gets a fixed "try again" reply.
- A message that asks for a human skips all of the above for that turn; see `human-escalation-sequence.md`.
