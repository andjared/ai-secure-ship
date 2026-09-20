---
name: plan-task
description: Plan how to implement one item from docs/DEV_PLAN.md (a checklist line, a week, or "the next task"). Reads the item, follows its references into REQUIREMENTS.md, inspects the current code, and returns a numbered implementation plan with no code. Use when the user asks to plan, walk through, or explore how to approach a DEV_PLAN task. Never edits files or writes code.
argument-hint: "[week number | pasted checklist item | e.g. second item of week 2]"
allowed-tools: Read, Grep, Glob, Agent, Bash(git log:*), Bash(git status:*), Bash(git diff:*)
---

Produce a plan only. Do not implement anything, and do not include code, pseudocode, function signatures or snippets. File paths and existing names are fine as references.

## 1. Resolve the target
- Use the argument: a week name or number, pasted checkbox text, or an ordinal like "second task".
- With no argument, take the first unchecked item in the earliest incomplete week.
- Checkboxes in `docs/DEV_PLAN.md` are often stale (finished work stays unticked). Cross-check against `git log` and the code before deciding what is done or next.
- If the target is truly ambiguous, ask one short question. Otherwise pick the sensible reading, state it in the first line, and continue.

## 2. Read the requirements trail
- Read the item's week section in `docs/DEV_PLAN.md`, including its Notes.
- Follow its Epic/Section references into `REQUIREMENTS.md` at the repo root. It is large, so Grep for the referenced headings and Read only those ranges.
- Collect the relevant user stories (acceptance criteria) and any non-functional rules.

## 3. Inspect the current code
- Read the files the item touches; use the Explore agent for broad searches.
- Note what already exists, what is missing, and constraints that change the approach, such as schema created by `create_all` with no migrations, or new routes needing the Vite proxy and an Orval regeneration.

## 4. Stay in scope
- Plan only the requested item. Put neighboring checklist items in a short "Left for later" list instead of planning them.

## 5. Write the plan
Use this shape:
1. **Context**: why the item exists and what it must achieve, in a few lines.
2. **Numbered steps**: for each, what to do, how, and which files or modules it touches.
3. **Tests / verification**: how to prove it works, including a deliberate failure case where relevant.
4. **Left for later**: adjacent items deliberately excluded.
5. **Open decisions**: each with a recommended default.

Keep it scannable. Prefer a recommendation over a survey of options.

## 6. Respect the project rules
Every plan must stay consistent with these:
- The identity gate is enforced server-side; the model never sets session state or `customer_id`.
- No PII in logs; failure messages are neutral and never reveal whether a record exists.
- The chat runs on the local Ollama model only.
- API types and hooks come from Orval-generated code, never hand-written.

## 7. Stop after planning
- If plan mode is active, write the plan to the plan file and request approval through the plan-mode exit.
- Otherwise present the plan in chat and wait for the user.
- Do not ask "does this look good?" in text, and do not start implementing.
