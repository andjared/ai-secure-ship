# Data Model (ERD)

Starting reference, copied from `SecureShip-5Week-Program.md` Section 6.4. See Section 4.4 for the mock data schema and Section 4.6 for the `CHAT_SESSION.transcript` JSONB column.

```mermaid
erDiagram
    CUSTOMER ||--o{ SHIPMENT : has
    SHIPMENT ||--o{ PACKAGE : contains
    CUSTOMER ||--o{ CHAT_SESSION : "may be linked to (post-verification)"
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
        string status
        string carrier
        string origin
        string destination
        date estimated_delivery
        datetime last_update
    }
    PACKAGE {
        uuid id PK
        uuid shipment_id FK
        string description
        decimal weight_kg
        decimal declared_value
    }
    CHAT_SESSION {
        uuid id PK
        uuid customer_id FK "nullable until Verified"
        string state
        datetime started_at
        datetime ended_at
        jsonb transcript
    }
    ADMIN_USER {
        string id PK
        string email
        string idp_subject
    }
```

> `ADMIN_USER` identity actually lives in Auth0; this row in the local DB (if mirrored) is a reference/audit record only, not the source of truth for credentials.
