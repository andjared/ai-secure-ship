# Admin and chat are separate identity systems (Epic E4)

Can an admin "become" a verified chat session, or can a chat session reach the admin API? This page records the checks. The short answer is no to both: admin login (Auth0) and the chat's identity gate share no code, no credential and no state.

## Why it holds by design

**An admin cannot become a verified chat session.**

- **One place verifies a session.** `check_code` in `backend/app/services/verification.py` is the only code that sets `ChatSession.customer_id` and moves a session to `verified`. The only other writer of `state` is `backend/app/services/identity.py`. Both are reached only from `/chat` and `/verify-code`.
- **The admin code never touches a chat session.** `backend/app/routes/admin.py`, `backend/app/services/admin_records.py` and `backend/app/services/admin_auth.py` import neither the `ChatSession` model nor any chat service, tool or LLM module.
- **The chat ignores the admin's token.** `/chat` and `/verify-code` read only the request body. An `Authorization` header changes nothing: the session starts `anonymous`, is offered no tool, and `run_tool` in `backend/app/tools/lookup_shipments.py` still refuses it.
- **No database link.** `ChatSession.customer_id` has no foreign key, so even deleting a customer cannot alter a session row.

**A chat session cannot reach the admin API.**

- **One admin check.** `require_admin` (`backend/app/services/admin_auth.py`) is attached once to the `/admin` router and accepts only an Auth0 access token issued by our tenant for our API. A chat `session_id` is not a token and is refused wherever it is put.
- **The chat code knows nothing about admin.** `routes/chat.py`, `routes/verify.py`, `services/identity.py`, `services/verification.py`, `services/escalation.py`, `tools/lookup_shipments.py` and `llm/` import nothing from the admin modules or the Auth0 SDK. The model's only tool is `lookup_shipments`.

**Frontend.** `App.tsx` renders either `AdminApp` or `ChatWindow`, never both. `Auth0Provider` wraps only `AdminApp`, and `useAdminAccessToken` adds the token only to requests whose URL starts with `/admin/`.

## Automated tests

`backend/tests/test_admin_records.py`, section *separation from chat*.

| Test | Attack or drift it guards against | Expected and asserted |
|---|---|---|
| `test_signed_in_admin_cannot_verify_a_chat_session` | A signed-in admin opens a chat, then creates, edits and deletes a customer, shipment and package | The chat session is still `anonymous` with no `customer_id`; the admin calls created no chat session |
| `test_admin_token_gives_the_chat_no_access` | An admin sends `/chat` with their bearer token and has the model call `lookup_shipments` for a customer they just created, then tries `/verify-code` with the token | No tool offered, the call returns `TOOL_UNAVAILABLE_RESULT`, no shipments; the session is not `verified` and has no `customer_id` |
| `test_verified_chat_session_cannot_reach_admin_routes` | A verified visitor presents their `session_id` to the admin API, as the bearer token and as a query/body parameter | 401 `invalid_token` and 400 `invalid_request`; no customer listed or written |
| `test_admin_code_imports_nothing_from_the_chat[...]` | A later change makes an admin module import the chat session model, a chat service, a tool or the LLM client | Fails, naming the import |
| `test_chat_code_imports_nothing_from_the_admin[...]` | A later change makes a chat module import the admin modules or the Auth0 SDK | Fails, naming the import |
| `test_only_admin_routes_carry_the_admin_check` | An admin route is mounted outside the `/admin` router, or a chat route picks up the admin check | The routes carrying `require_admin` are exactly the app's `/admin` routes |

The two import tests check the modules named in `ADMIN_MODULES` and `CHAT_MODULES`; add a new admin or chat module to the matching list.

They sit next to the E3 tests in the same file (`test_admin_routes_refuse_a_request_without_a_token`, `test_admin_routes_refuse_a_malformed_token`).

Run them with:

```bash
cd backend && pytest tests/test_admin_records.py -k "chat or admin_check or admin_token"
```

## Manual checks

1. Log in at http://localhost:3000/admin, then open http://localhost:3000/ in the same browser. The chat starts anonymous and still asks for the four identity details.
2. In the browser's network tab, `/chat` and `/verify-code` requests carry no `Authorization` header; `/admin/` requests do.
3. Verify in the chat as a seeded customer, copy the `session_id` from a `/chat` request, then:
   ```bash
   curl -i -H "Authorization: Bearer <session_id>" http://localhost:8000/admin/customers
   ```
   The answer is 401 `invalid_token`.

## What this does not claim

An admin can create a customer with details they choose and then pass the chat gate as that customer, like any visitor who knows the four details and the code. With the mock 2FA the code is printed in the backend log, so anyone who can read that log can do the same. This is not a path between the two systems: it goes through the same gate as every visitor, and it shows the admin nothing the admin panel does not already show. Real SMS delivery would close it for everyone but the phone's owner.
