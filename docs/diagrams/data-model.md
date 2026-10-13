# Data Model (ERD)

As implemented (`backend/app/models/`). Tables are created by `Base.metadata.create_all` on startup; there are no migrations.

```mermaid
erDiagram
    CUSTOMER ||--o{ SHIPMENT : has
    SHIPMENT ||--o{ PACKAGE : contains
    CUSTOMER |o..o{ CHAT_SESSION : "linked after verification (no FK constraint)"
    CUSTOMER {
        uuid id PK
        string first_name
        string last_name
        string phone_number
        string address
    }
    SHIPMENT {
        uuid id PK
        uuid customer_id FK
        string tracking_number
        enum status
        string carrier
        string origin
        string destination
        date estimated_delivery
        timestamptz last_update "always set by the server"
    }
    PACKAGE {
        uuid id PK
        uuid shipment_id FK
        string description
        numeric weight_kg "6,2"
        numeric declared_value "10,2"
    }
    CHAT_SESSION {
        uuid id PK
        uuid customer_id "nullable, set only by check_code"
        enum state
        timestamptz started_at
        timestamptz ended_at "nullable, never written"
        jsonb transcript
        jsonb pending_identity
    }
```

Table names are `customers`, `shipments`, `packages` and `chat_sessions`.

- **`shipments.status`**: `label_created`, `in_transit`, `out_for_delivery`, `delivered`, `exception`.
- **`chat_sessions.state`**: `anonymous`, `collecting_identity`, `code_sent`, `awaiting_code`, `verified`, `escalated_to_human` (the last one is never used; see `identity-gating-state-machine.md`).
- **`chat_sessions.customer_id`** is a plain nullable UUID column, not a database foreign key, which is why the link above is dashed. It stays empty until the code is verified.
- **`chat_sessions.transcript`** is a list of turns: `role` (`user`, `assistant` or `system`), `content`, `timestamp`, plus an optional `event` (`escalated_to_human` on the scripted handoff lines) and optional `tool_calls` (names of tools the model called on that turn).
- **`chat_sessions.pending_identity`** holds the unverified details the visitor typed (`first_name`, `last_name`, `address`, `phone_number`) while they are being collected.
- **Deletes** have no database cascade; the admin service removes packages, then shipments, then the customer.
- **Not in the database:** verification codes (in backend memory only) and admin users (they exist only in Auth0).
