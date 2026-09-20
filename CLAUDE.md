# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SecureShip: a shipment-support chat where the AI may only reach customer shipment data after the visitor passes an identity + mock-2FA gate. Product spec is `REQUIREMENTS.md` (large; grep for the Epic/Section you need). The build is planned week by week in `docs/DEV_PLAN.md`; its checkboxes are often stale, so check `git log` and the code for what is actually done. Architecture diagrams (state machine, tool-calling sequences, data model) are in `docs/diagrams/`.

## Commands

Full stack: `docker compose up` (frontend :3000, backend :8000, Postgres :5432). Ollama is **not** in Docker; run `ollama serve` on the host (model `qwen3:8b`, reached from the backend container at `host.docker.internal:11434`).

Native dev (Postgres in Docker, see README for details):
```bash
docker compose up -d postgres
cd backend && source .venv/bin/activate
export DATABASE_URL=postgresql://user:pass@localhost:5432/secureship OLLAMA_HOST=http://localhost:11434
uvicorn app.main:app --port 8000 --reload
cd frontend && npm run dev          # also: npm run build (tsc -b + vite build), npm run lint (oxlint)
```
Don't run the Docker backend/frontend and native processes together (port clashes).

Backend tests (need Postgres running; `pip install -r requirements-dev.txt`):
```bash
cd backend && pytest                                   # all
pytest tests/test_identity_matching.py -k phone        # one file / one test by keyword
```
Tests create and use a separate `secureship_test` database (`TEST_DATABASE_URL` overrides the default) and never touch dev data.

Seed mock customers/shipments/packages (idempotent): `docker compose exec backend python -m scripts.seed_data`

Regenerate the frontend API client (backend must be running on :8000): `cd frontend && npm run generate-api`

## Architecture

- **Backend** (`backend/app`): FastAPI + sync SQLAlchemy 2.0 on Postgres. `routes/` holds HTTP handlers, `services/` holds the security logic (currently `identity.py`), `llm/` wraps Ollama, `models/` the ORM. There are no migrations: `Base.metadata.create_all` runs on startup, so adding a column to an existing table does nothing until that table is dropped (`docker compose down -v` or drop it in psql). The test conftest has the same limitation with the persistent test DB.
- **Chat flow**: `POST /chat` (`operation_id="sendChatMessage"`) loads or creates a `ChatSession`, appends the user turn to the JSONB `transcript`, calls Ollama over HTTP (`llm/ollama_client.py`, non-streaming), appends the reply, commits. `transcript` is reassigned to a new list on each turn so SQLAlchemy detects the change; keep doing that instead of mutating in place.
- **Session state machine** (`models/chat_session.py`, spec in REQUIREMENTS 6.2): `anonymous → collecting_identity → code_sent → awaiting_code → verified`, plus `escalated_to_human`. `IdentityRejected` and `CodeExpired` in the diagram are not enum values.
- **Identity matching** (`services/identity.py`): `match_customer` requires all four fields (first name, last name, address, phone) to match the same single customer after normalization, and returns a customer id or `None` with no failure reason. Callers must show `IDENTITY_NOT_VERIFIED_MESSAGE`. Not yet wired into `/chat`.
- **Frontend** (`frontend/src`): React 19 + Vite + React Query. The API client is Orval output in `src/api/generated/chat.ts`, generated from the backend's live OpenAPI schema (`frontend/orval.config.ts`). The Vite dev proxy forwards only `/chat` and `/health`; a new backend route needs a proxy entry in `vite.config.ts` as well as a regeneration.

## Project rules

- The identity gate is enforced server-side. The model never sets session `state` or `customer_id`; the backend decides all transitions.
- No PII in logs. Failure messages are neutral and never reveal whether a customer, phone or address exists.
- The LLM is local Ollama only.
- API types and hooks come only from Orval-generated code. Never hand-write or hand-edit them; regenerate.

## Project skills

`.claude/skills/`: `plan-task` (plan a DEV_PLAN item, no code) and `orval-regen-check` (suggest regenerating the client when backend API changes leave it stale; it never runs Orval).
