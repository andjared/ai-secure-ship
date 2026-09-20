---
name: orval-regen-check
description: Notice when the Orval-generated frontend API client (frontend/src/api/generated/) is stale after backend API changes, and suggest regenerating it. Use after editing backend routes, request/response Pydantic models, or FastAPI app setup, or when asked whether the generated client is up to date. Only suggests; never runs Orval, never starts the backend, never edits generated files.
argument-hint: "[optional: backend file or change to check]"
allowed-tools: Read, Grep, Glob, Bash(git log:*), Bash(git status:*), Bash(git diff:*)
---

Check whether the generated client has fallen behind the backend API, and if so, suggest regenerating. Suggest only.

## 1. Hard rules
- Never run `orval`, `npx orval`, `npm run generate-api`, or anything else that regenerates the client or starts the backend. The user runs it.
- Never edit anything under `frontend/src/api/generated/`, and never hand-write API types or hooks as a workaround. Generated output comes only from Orval.
- Suggest only when the client is actually stale (section 3). If nothing is stale, say nothing about Orval.

## 2. Backend files that can change the OpenAPI schema
Flag a change in any of these:
- `backend/app/routes/*.py`: routes, HTTP methods, paths, `operation_id`, `response_model`, `status_code`, path/query/body parameters, and the Pydantic `BaseModel` request/response classes defined there (currently `ChatRequest` and `ChatResponse`). A new route module counts too.
- Any Pydantic schema module used by routes (for example a future `backend/app/schemas/`).
- `backend/app/main.py`: `FastAPI(...)` arguments (title, version, `openapi_*`), `include_router` (prefix, tags), and routes declared directly on `app` such as `/health`.
- `backend/app/models/*.py`, only when an enum or type from there is exposed through a route's request or response model (for example `SessionState` appearing in a response). Plain ORM column changes do not count.

These do not affect the schema, so ignore them: `backend/app/services/`, `backend/app/llm/`, `backend/app/db/`, `backend/tests/`, `backend/scripts/`, `requirements*.txt`, the Dockerfile, and ORM-only model changes.

## 3. Decide whether the client is really stale (read-only)
- Find what changed: `git status`, `git diff` (staged and unstaged), and `git log` for the backend trigger files since the last commit that touched `frontend/src/api/generated/`.
- Read the diff. A docstring or internal-logic edit in a route file does not change the API surface; a path, method, `operation_id`, field, type, default, or enum value does.
- Confirm against `frontend/src/api/generated/chat.ts` with Grep/Read: each route path and `operation_id`, each request/response schema name and its fields, and each exposed enum value in the backend should appear there with the same shape. Something missing or different proves the client is stale.
- Do not suggest when the generated file already reflects the change (regenerated in the same diff or a later commit, or the content matches).
- Commit order or timestamps alone are not proof; use the content check.

## 4. When it is stale, say this (one short block)
- Which backend files changed and what is out of date in the client, for example: "`POST /verify-code` and `VerifyCodeRequest` are not in `chat.ts`".
- The command for the user to run, and its prerequisite: the backend must be running at `localhost:8000`, then `cd frontend && npm run generate-api`. Offer it as `! cd frontend && npm run generate-api` so it runs in this session on their say-so.
- If a route was added, note that the Vite proxy forwards only `/chat` and `/health`, so the new path needs a proxy entry in the frontend Vite config. Mention it; do not change it.
- After they regenerate, offer to check frontend usages of any renamed or removed hooks and types. Do not do it unprompted.

## 5. Project rule
API types and hooks come only from Orval-generated code. A stale client is fixed by regenerating, never by editing `chat.ts` or typing the shapes by hand.
