# memory-search-chat-demo

A small chat demo focused on combining multi-turn conversation, session memory, project-level context, search, and controlled cross-session reads in one clear codebase.

## Current Capabilities

- `POST /api/chat` chat API
- SQLite persistence for `Project`, `ChatSession`, `ChatMessage`, `SessionSummary`, and `ProjectStableFact`
- Project and session management APIs
- Editable project name, project instruction, and project description
- Project-level stable facts / saved memories management
- Context read rules based on `Project.access_mode` and `ChatSession.is_private`
- Full session message history readback
- Automatic session title generation and manual rename
- Static frontend console for chat, project/session management, and debug fields

## Current Data Semantics

- `ChatMessage`: source of truth for real conversation history
- `working_memory`: runtime handoff memory for continuing the current session
- `session_digest`: cross-session readable session overview
- `Project.instruction`: project-level model instruction and primary project prompt field
- `Project.description`: human-readable project note; never injected into model context
- `ProjectStableFact`: project-level long-term stable fact or constraint
- `SessionSummary`: derived storage only; currently stores `working_memory` and `session_digest`

## Current Model Context Order

`LLMService` currently injects context in this order:

1. `SYSTEM_PROMPT`
2. `project.name` + `project.instruction`
3. active project `stable_facts`
4. current session `working_memory`
5. related session `session_digest`
6. search results
7. recent messages
8. current user message

Notes:

- `project.description` does not enter model context
- `access_mode` only controls access boundaries
- derived memory does not replace `ChatMessage` history

## Frontend Restore Logic

The frontend only keeps lightweight UI state in `localStorage`:

- `backendBaseUrl`
- `currentProjectId`
- `currentSessionId`
- sidebar expand/collapse state

After refresh, the frontend:

1. restores the selected project/session IDs
2. reloads project and session lists
3. reloads full message history through `GET /api/sessions/{session_id}/messages`
4. reloads `working_memory` and `session_digest` through `GET /api/sessions/{session_id}/summary` for debug display only
5. reloads project stable facts on demand when the project modal opens

What it does not do:

- it does not persist full message history in local frontend storage
- it does not locally cache stable facts beyond current page state
- it does not restore transient debug snapshots after refresh

## Project Field Roles

- `name`: human-facing project topic name and weak prompt signal
- `instruction`: project-level model instruction
- `description`: human-readable project note
- `access_mode`: access boundary control; immutable after project creation

## Delete and Archive Rules

- archived sessions remain queryable but cannot continue chatting and do not enter context resolution
- deleting a session is a hard delete and cascades to messages and derived memory
- deleting a project is a hard delete and cascades to sessions, messages, derived memory, and stable facts
- archiving a stable fact removes it from model context
- project archive is not implemented

## Quick Start

### Backend

```bash
uvicorn backend.app.main:app --reload
```

### Frontend

```bash
cd frontend
python -m http.server 5500
```

Open:

```text
http://127.0.0.1:5500
```

## Tests

```bash
pytest -q
```

## Current Boundaries and Backlog

Not implemented today:

- message pagination / lazy loading
- stable facts auto extraction
- embedding / vector retrieval
- cross-session full-message reads
- agent loop / tool orchestration framework

This README describes current behavior only. It does not promise future features.
