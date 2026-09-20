# SecureShip

AI-gated shipment support chat app, built per [`REQUIREMENTS.md`](./REQUIREMENTS.md). See [`DEV_PLAN.md`](/docs/DEV_PLAN.md) for the week-by-week build plan.

> This README is a Week 1 stub. It will be regenerated against the real implementation in Week 5 (Section 7.1 of the program doc).

## Stack

- **Frontend:** React + TypeScript (Vite)
- **Backend:** FastAPI (Python)
- **Database:** Postgres
- **Local LLM:** Ollama, running on the host (not in Docker — see `docs/diagrams/deployment-topology.md`)

## Running locally

```bash
docker-compose up
```

- Frontend: http://localhost:3000
- Backend health check: http://localhost:8000/health
- Postgres: localhost:5432

Ollama must be installed and running on the host separately (`ollama serve`), reachable from the backend container at `host.docker.internal:11434`.

## Running locally without Docker

Postgres can stay in Docker while the backend and frontend run natively — useful for live code reload.

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Keep Postgres running via Docker (from the repo root):

```bash
docker compose up -d postgres
```

Set env vars (these differ from the in-container values — `host.docker.internal` only resolves inside a container):

```bash
export DATABASE_URL=postgresql://user:pass@localhost:5432/secureship
export OLLAMA_HOST=http://localhost:11434
```

Then run with live reload:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Ollama must still be running on the host (`ollama serve`), same as the Docker path.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Serves on http://localhost:3000, same as the Docker path.

> Don't run both the Docker `backend`/`frontend` containers and the native processes at the same time — they'd conflict on ports 8000/3000.

## Inspecting the database

Postgres runs in the `postgres` container regardless of whether the backend runs in Docker or natively. Connect to it with `psql` via `docker compose exec`:

```bash
# Interactive session
docker compose exec postgres psql -U user -d secureship
```

Once inside, a few useful commands:

```sql
\dt              -- list all tables
\d customers     -- show a table's columns and types
\q               -- quit
```

Or run one-off queries without opening an interactive session:

```bash
# List tables
docker compose exec postgres psql -U user -d secureship -c "\dt"

# Peek at some rows
docker compose exec postgres psql -U user -d secureship -c "select * from customers limit 5;"
docker compose exec postgres psql -U user -d secureship -c "select * from shipments limit 5;"

# Row counts
docker compose exec postgres psql -U user -d secureship -c "select count(*) from customers;"

# Shipment status distribution
docker compose exec postgres psql -U user -d secureship -c "select status, count(*) from shipments group by status;"

# A session's stored conversation transcript
docker compose exec postgres psql -U user -d secureship -c "select id, state, transcript from chat_sessions;"
```

Prefer a GUI? Point a client like TablePlus, DBeaver, or Postico at `localhost:5432`, database `secureship`, user `user`, password `pass` (from `docker-compose.yml`).

To (re)populate the `customers`/`shipments`/`packages` tables with mock data, run the seed script inside the backend container:

```bash
docker compose exec backend python -m scripts.seed_data
```

It's idempotent — safe to re-run, it clears and regenerates rather than accumulating duplicates.

## Repo layout

```text
secureship/
├── docker-compose.yml
├── docs/diagrams/     # architecture diagrams (Section 6 of the program doc)
├── frontend/          # React + Vite chat UI
└── backend/           # FastAPI app
    └── scripts/       # mock data seeding, etc.
```
