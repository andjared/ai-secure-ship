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

## Repo layout

```text
secureship/
├── docker-compose.yml
├── docs/diagrams/     # architecture diagrams (Section 6 of the program doc)
├── frontend/          # React + Vite chat UI
├── backend/           # FastAPI app
└── scripts/           # mock data seeding, etc.
```
