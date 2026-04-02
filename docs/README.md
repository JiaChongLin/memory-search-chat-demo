# Docs

The `docs/` directory records the current architecture, API surface, and implementation notes.

Key terminology is now aligned with the live codebase:

- `working_memory` is the current session's runtime handoff memory
- `session_digest` is the cross-session readable session overview
- `related_session_digest_count` is the primary debug field name
- `/api/sessions/{session_id}/summary` is a legacy route name kept for compatibility; it returns derived memory state, not a single generic summary

## Index

- `api.md`
  Chat API, project/session management API, and debug field definitions.
- `architecture.md`
  Service boundaries, context resolution flow, and how derived memory enters the chat chain.
- `project-plan.md`
  Stage plan and current scope.
- `dev-notes.md`
  Short implementation notes and compatibility guidance.
