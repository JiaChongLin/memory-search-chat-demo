# Dev Notes

## Terminology

- `ChatMessage` is the source of truth.
- `SessionSummary` is a derived table, not a history source.
- `working_memory` is the current session runtime handoff memory.
- `session_digest` is the session overview exposed to other sessions.
- `stable_facts` are project-level long-term facts or constraints.
- `Project.instruction` is the project-level prompt field.
- `Project.description` is human-readable only.

## Compatibility Notes

- `GET /api/sessions/{session_id}/summary` keeps its old route name for compatibility.
  It returns `{ working_memory, session_digest, summary_updated_at }`.
- `related_summary_count` remains as a deprecated compatibility alias.
  New code should use `related_session_digest_count`.
- Frontend state uses `memoryMap`, not `summaryMap`.

## Current Rules

- current-session continuation reads `recent messages + working_memory`
- cross-session reads use `session_digest` only
- `project.description` never enters model context
- active stable facts enter model context only when the current session belongs to that project
- debug UI should name `working_memory` and `session_digest` explicitly instead of using generic `summary` wording

## Out of Scope

- message pagination
- vector retrieval
- stable facts auto extraction
- cross-session full-message reads
- agent loop
