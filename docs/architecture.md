# Architecture

## Overview

This repository is an application-style chat demo, not a general-purpose agent platform. The current goal is to keep session memory, project context, search, and controlled cross-session reads working together in one simple stack.

## Main Layers

- API Router: request parsing and response shaping
- `ChatService`: top-level chat orchestration
- `ContextResolver`: readable-context resolution under project/session rules
- `MemoryService`: message writes and derived memory maintenance
- `StableFactService`: project-level stable fact CRUD
- `SessionService` / `ProjectService`: session and project management
- `LLMService`: context assembly and model call
- Frontend Static Console: management and debugging UI

## Responsibilities

### `ChatService`

`ChatService` is responsible for:

1. resolving current request context
2. deciding whether search should run
3. calling `LLMService`
4. persisting `ChatMessage` and derived memory
5. attempting automatic session naming without blocking chat success

### `ContextResolver`

`ContextResolver` currently resolves:

- current session recent messages
- current session `working_memory`
- current project's `name` and `instruction`
- current project's active `stable_facts`
- readable `session_digest` objects from other sessions

Important rules:

- `project.description` is excluded from model context
- cross-session reads use `session_digest` only
- other sessions' full message history is not injected

### `MemoryService`

`MemoryService` currently handles:

- `ChatMessage` writes
- recent message reads
- `working_memory` generation and persistence
- `session_digest` generation and persistence
- session metadata updates such as `message_count`, `last_message_at`, and `summary_updated_at`

### `StableFactService`

`StableFactService` manages project-level long-term facts:

- CRUD for `ProjectStableFact`
- `active` vs `archived` status
- separation from message history and session-derived memory

## Current Semantics

- `ChatMessage` is the source of truth
- `working_memory` is for continuing the current session
- `session_digest` is for cross-session and project-level reads
- `Project.instruction` is the project-level prompt field
- `Project.description` is human-readable only
- `ProjectStableFact` is project-level long-term information
- `SessionSummary` is derived storage, not a history source

## Current Context Injection Order

`LLMService` currently injects context in this order:

1. `SYSTEM_PROMPT`
2. `project.name` + `project.instruction`
3. active `stable_facts`
4. current session `working_memory`
5. related `session_digest`
6. search results
7. recent messages
8. current user message

The implementation also applies lightweight per-section limits for:

- stable facts count and section length
- related digest count and section length
- search result count and section length
- project instruction and working memory length

This is still a simple layered prompt assembly, not a prompt-builder framework.

## Frontend Restore Logic

The frontend restore flow is intentionally lightweight:

- `localStorage` stores backend URL, selected project/session IDs, and sidebar UI state
- `GET /api/sessions/{session_id}/messages` restores real message history after refresh
- `GET /api/sessions/{session_id}/summary` restores `working_memory` and `session_digest` for debug display
- `GET /api/projects/{project_id}/stable-facts` loads project stable facts on demand in the project modal

The frontend does not:

- persist full message history locally
- persist stable facts as a separate long-term frontend cache
- restore transient in-page debug snapshots after refresh

## Out of Scope Today

The current architecture does not include:

- cross-session full-message reads
- embedding / vector retrieval
- stable facts auto extraction
- agent loop
- general tool runtime infrastructure

Those remain backlog items, not current architecture.
