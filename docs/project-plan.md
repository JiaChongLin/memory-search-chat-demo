# Project Plan

## Goal

Evolve the current chat demo into a small system with project-level organization, session-level memory, controlled cross-session reads, and lightweight search integration, while keeping the implementation easy to inspect and extend.

## Completed Milestones

### 1. Project and session management

Completed:

- `Project` model and project management API
- `ChatSession.project_id`, `status`, and `is_private`
- project access boundaries: `open | project_only`
- session visibility switch: `is_private`

### 2. Context resolution under access rules

Completed:

- current session prioritizes its own recent messages
- current session continuation reads its own `working_memory`
- other sessions contribute `session_digest` only
- private sessions are not exposed to other sessions
- archived sessions do not participate in context resolution

### 3. Project-level prompt and long-term memory layers

Completed:

- `Project.instruction` enters model context
- `Project.description` is reduced to a human-readable field
- project-level `stable_facts` enter model context
- single-summary behavior has been split into `working_memory` + `session_digest`

### 4. Frontend management and restore flow

Completed:

- project and session management console
- full message history readback
- lightweight frontend restore flow
- derived-memory debug display

## Current Model Context

The model currently receives:

- `SYSTEM_PROMPT`
- `project.name` + `project.instruction`
- active `stable_facts`
- current session `working_memory`
- related `session_digest`
- search results
- recent messages

The model currently does not receive:

- `project.description`
- other sessions' full raw messages
- inactive / archived stable facts
- archived sessions
- private sessions from other conversations

## Current Delete and Archive Rules

- archived sessions remain stored but cannot continue chatting or enter context resolution
- session delete is a hard delete
- project delete is a cascading hard delete
- stable facts can be archived to disable context injection
- project archive is not implemented

## Backlog

- message pagination / lazy loading
- stable facts extraction and confirmation flow
- stronger derived-memory validation and rebuild tools
- embedding / vector retrieval
- cross-session full-message reads
- agent loop / tool runtime
