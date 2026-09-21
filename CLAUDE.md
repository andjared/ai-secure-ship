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
- **Identity collection** (`services/identity.py`, used by `/chat`): while a session is `anonymous` or `collecting_identity`, `llm/ollama_client.py` `extract_identity` makes a separate structured-output Ollama call that returns the four details plus an "asks about a shipment" flag. `collect_identity` is the only code that moves `anonymous → collecting_identity`, and it keeps a detail only if it visibly appears in the visitor's message. Details accumulate in `ChatSession.pending_identity` (JSONB, reassign a new dict on change). Once all four are present `/chat` matches them (see below) and replies with `IDENTITY_COLLECTED_MESSAGE` on a hit or `IDENTITY_NOT_VERIFIED_MESSAGE` on a miss, never a model reply.
- **Identity matching** (`services/identity.py`): `match_customer` requires all four fields (first name, last name, address, phone) to match the same single customer after normalization, and returns a customer id or `None` with no failure reason. Callers must show `IDENTITY_NOT_VERIFIED_MESSAGE`. `/chat` runs it through `check_collected_identity` once all four details are collected: a hit moves the session to `code_sent` without setting `customer_id` (that waits for verification), a miss clears `pending_identity` and the session stays `collecting_identity`.
- **Frontend** (`frontend/src`): React 19 + Vite + React Query. The API client is Orval output in `src/api/generated/chat.ts`, generated from the backend's live OpenAPI schema (`frontend/orval.config.ts`). The Vite dev proxy forwards only `/chat` and `/health`; a new backend route needs a proxy entry in `vite.config.ts` as well as a regeneration.

## Project rules

- The identity gate is enforced server-side. The model never sets session `state` or `customer_id`; the backend decides all transitions.
- No PII in logs. Failure messages are neutral and never reveal whether a customer, phone or address exists.
- The LLM is local Ollama only.
- API types and hooks come only from Orval-generated code. Never hand-write or hand-edit them; regenerate.

## General rules

- Finish the requested task first. Only then suggest improvements, and keep them out of the same change unless the user asks.
- Keep it simple and maintainable: the smallest change that solves the problem, no speculative abstractions, no code for hypothetical future needs.
- Prefer modifying existing code over adding new functionality. Search for an existing function, component, or module to extend before writing a new one.
- Do not add dependencies (pip or npm) unless absolutely necessary. First check whether the stdlib, FastAPI/SQLAlchemy, React, or React Query already covers it, and say why if one is unavoidable.
- Don't refactor, rename, or reformat code unrelated to the task.

## Adding new functionality

- Explore first: before writing anything, search the codebase (grep for related names, check the folder where it would live) for something that already does the job or most of it.
- Reuse what exists. Don't duplicate logic, constants, types or components; if you need the same thing twice, share it instead of copying.
- When appropriate, extend an existing module, function, component or model rather than writing a new one, for example by adding a parameter or a small branch instead of a near-copy.
- Write something new only when nothing existing fits, and keep it minimal. In your summary, mention what you looked at and why you didn't reuse it.

## Project structure

- Follow the existing layout (`backend/app/{routes,services,llm,models,db}`, `frontend/src/{api,components}`, `docs/`). Put new code in the folder that already fits its role.
- Don't create new folders unless nothing existing fits. Always try to reuse an existing folder first; when a new one is truly needed, say why.
- Don't add a new file for one-off code that belongs in an existing file. Backend tests go in `backend/tests/`.

## Naming

- Names are simple and self-explanatory: say what a thing is or does (`match_customer`, `IDENTITY_NOT_VERIFIED_MESSAGE`), not how it is implemented.
- No vague or generic names (`data`, `handler2`, `utils`, `helper`, `manager`) and no abbreviations beyond well-known ones (`id`, `db`).
- Match existing conventions: Python `snake_case` functions/modules and `PascalCase` classes; React components `PascalCase`, hooks `useCamelCase`, other TS variables/functions `camelCase`.
- Functions start with a verb; booleans read as questions (`isPending`, `is_verified`).

## Architecture rules

- Backend layers: `routes/` handles HTTP only (parse the request, call a service, shape the response). Security and business logic live in `services/`. `llm/` only talks to Ollama. `models/` is ORM only. Routes hold no business rules, and services never import from `routes/`.
- Security decisions live in one auditable place in the backend; never scatter "is the session verified" checks.
- Keep functions small and single-purpose. Pass dependencies such as the DB session in via FastAPI `Depends` instead of creating them inside functions.
- New service or security logic gets tests in `backend/tests/`.
- A new route needs an `operation_id`, typed Pydantic request/response models, an Orval regeneration and a Vite proxy entry.

## Frontend rules

- **Components:** function components only, one per file in `components/<Name>/`, small and focused. Split a component that does more than one job.
- **TypeScript:** no `any` (use `unknown` and narrow). Type props with an interface or type. Avoid `as` assertions unless unavoidable. Reuse the Orval-generated types instead of redefining API shapes.
- **Hooks:** call hooks at the top level only. Extract non-trivial or reusable stateful logic into a custom `useX` hook. Keep effect dependency arrays honest, and don't use `useEffect` for anything that can be derived during render or handled in an event handler. Server state goes through the generated React Query hooks, never local `useState` plus fetch.
- **No prop drilling:** don't pass props through components that don't use them. Prefer composition (`children`), keeping state close to where it is used, or React Context for state shared across distant components (e.g. the chat session).
- Keep styles with their component (the existing `Component.css` pattern). No new UI or state libraries.
- Run `npm run lint` and `npm run build` after frontend changes.

## Project skills

`.claude/skills/`: `plan-task` (plan a DEV_PLAN item, no code) and `orval-regen-check` (suggest regenerating the client when backend API changes leave it stale; it never runs Orval).
