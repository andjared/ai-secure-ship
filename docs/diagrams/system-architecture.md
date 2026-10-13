# System Architecture

As implemented (`backend/app/main.py`, `routes/`, `services/`, `tools/`, `llm/`, `frontend/src/App.tsx`, `frontend/src/main.tsx`):
- The chat and the admin area are two halves that share the database and nothing else: no shared code, state or login.
- There is no separate session store. A session's `state`, `customer_id`, collected details and transcript all live on its `chat_sessions` row in Postgres. The only in-memory piece is the verification-code dict in `services/verification.py`.
- The model never calls a tool to collect or check identity. The backend runs those steps itself; the model is only asked to extract details from text and to write replies.
- The mock SMS is a backend log line.
- The admin check is a router-level dependency (`require_admin`) on the `/admin` router, not app middleware.

```mermaid
flowchart TB
    subgraph Client["Browser (React 19 + Vite, Orval-generated client)"]
        ChatUI["ChatWindow<br/>(every path except /admin)"]
        Modal["CodeModal<br/>(opened on event: code_sent)"]
        AdminUI["AdminApp at /admin<br/>(Auth0Provider, AdminGate, AdminPanel)"]
    end

    subgraph Backend["Backend (FastAPI)"]
        subgraph Routes["routes/"]
            ChatAPI["POST /chat"]
            VerifyAPI["POST /verify-code"]
            AdminAPI["/admin/* (customers, shipments, packages)"]
        end
        subgraph Services["services/"]
            Identity["identity<br/>(collect details, match customer)"]
            Verification["verification<br/>(issue and check codes,<br/>only place that sets verified)"]
            Codes["in-memory codes<br/>(code, expiry, attempts,<br/>matched customer id)"]
            Escalation["escalation<br/>(scripted handoff lines)"]
            AdminAuth["admin_auth.require_admin<br/>(Auth0 token validation)"]
            AdminRecords["admin_records<br/>(create, edit, delete)"]
        end
        ToolLayer["tools/lookup_shipments.run_tool<br/>(enforcement point: verified session only,<br/>customer read from the session)"]
        LLMClient["llm/ollama_client<br/>(extract_identity, chat + tool-call loop)"]
    end

    subgraph LocalLLM["Local LLM (on the host)"]
        Ollama["Ollama :11434<br/>model qwen3:8b"]
    end

    subgraph DataLayer["Postgres"]
        ChatDB[("chat_sessions<br/>state, customer_id,<br/>pending_identity, transcript")]
        DB[("customers / shipments / packages")]
    end

    subgraph IdP["Identity Provider"]
        Auth0["Auth0<br/>(admin login ONLY)"]
    end

    ChatUI -->|"message + session_id"| ChatAPI
    ChatUI -->|"on event: code_sent"| Modal
    Modal -->|"session_id + code"| VerifyAPI

    ChatAPI -->|"load session, append turns"| ChatDB
    ChatAPI -->|"asks for a human?"| Escalation
    ChatAPI -->|"anonymous or collecting_identity"| Identity
    ChatAPI -->|"identity matched: issue code"| Verification
    ChatAPI -->|"extract details / get reply<br/>(tool offered only when verified)"| LLMClient
    LLMClient -->|"HTTP /api/chat"| Ollama
    LLMClient -->|"each tool call the model makes"| ToolLayer
    Identity -->|"match all four fields"| DB
    ToolLayer -->|"shipments of session.customer_id"| DB

    VerifyAPI --> Verification
    Verification --- Codes
    Verification -->|"mock SMS"| Log["backend log"]
    VerifyAPI -->|"save state, customer_id, reply"| ChatDB

    AdminUI -->|"login redirect"| Auth0
    Auth0 -->|"access token"| AdminUI
    AdminUI -->|"requests + Bearer token"| AdminAPI
    AdminAPI --> AdminAuth
    AdminAuth -.->|"signing keys"| Auth0
    AdminAPI -->|"if token valid"| AdminRecords
    AdminRecords --> DB

    style ToolLayer fill:#ffe6cc,stroke:#d79b00,stroke-width:2px
    style AdminAuth fill:#ffe6cc,stroke:#d79b00,stroke-width:2px
```

The two highlighted boxes are the only access checks: `run_tool` for shipment data in the chat, `require_admin` for the admin API. `admin_records` never reads or writes `chat_sessions` (see `docs/admin-chat-separation.md`).
