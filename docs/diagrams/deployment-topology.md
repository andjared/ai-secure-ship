# Deployment / Local Dev Topology

As implemented (`docker-compose.yml`, `frontend/Dockerfile`, `backend/Dockerfile`, `frontend/src/main.tsx`, `backend/.env.example`, `frontend/.env.example`). Ollama runs on the host, not in Docker.

```mermaid
flowchart LR
    subgraph DevMachine["Developer machine"]
        direction TB

        Browser[Browser]

        subgraph Compose["docker compose up"]
            direction TB
            ReactC["frontend container<br/>Vite dev server :3000"]
            PyC["backend container<br/>uvicorn :8000"]
            PgC[("postgres:16 container<br/>:5432, volume pgdata")]
        end

        OllamaHost["Ollama on the HOST<br/>:11434, model qwen3:8b"]
    end

    subgraph Cloud["External service"]
        AuthProvider["Auth0<br/>(admin login only)"]
    end

    Browser -->|"loads the app<br/>localhost:3000"| ReactC
    Browser -->|"REST/JSON, CORS<br/>localhost:8000"| PyC
    PyC -->|"DATABASE_URL<br/>postgres:5432"| PgC
    PyC -->|"OLLAMA_HOST<br/>host.docker.internal:11434"| OllamaHost
    Browser -.->|"admin login redirect"| AuthProvider
    PyC -.->|"token validation keys"| AuthProvider

    style Compose fill:#e6f2ff,stroke:#3380cc,stroke-width:2px
    style OllamaHost fill:#fff4e6,stroke:#cc8800,stroke-width:2px
```

Notes:
- There is no proxy between the frontend and the backend. The browser gets the app from `:3000` and then calls the API on `:8000` directly (`axios.defaults.baseURL`); the backend's CORS allows only `http://localhost:3000`.
- The backend reads `AUTH0_DOMAIN` and `AUTH0_AUDIENCE` from `backend/.env` and will not start without them. The frontend reads `VITE_AUTH0_DOMAIN`, `VITE_AUTH0_CLIENT_ID` and `VITE_AUTH0_AUDIENCE` from `frontend/.env`.
- Native dev runs the same three processes on the same ports with only Postgres in Docker; the backend then reaches Ollama at `localhost:11434`. Don't run both setups at once.
- Verification codes are mock 2FA written to the backend log; no SMS provider is involved.
