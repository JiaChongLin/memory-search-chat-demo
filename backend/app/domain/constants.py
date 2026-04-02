from __future__ import annotations

from typing import Literal


PROJECT_ACCESS_OPEN = "open"
PROJECT_ACCESS_PROJECT_ONLY = "project_only"
PROJECT_ACCESS_MODES = (
    PROJECT_ACCESS_OPEN,
    PROJECT_ACCESS_PROJECT_ONLY,
)

SESSION_VISIBILITY_SHARED = "shared"
SESSION_VISIBILITY_PRIVATE = "private"
SESSION_VISIBILITY_MODES = (
    SESSION_VISIBILITY_SHARED,
    SESSION_VISIBILITY_PRIVATE,
)

STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"
RECORD_STATUSES = (
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
)

RELATED_SESSION_DIGEST_SOURCE_PROJECT = "project"
RELATED_SESSION_DIGEST_SOURCE_EXTERNAL = "external"
RELATED_SESSION_DIGEST_SOURCE_SCOPES = (
    RELATED_SESSION_DIGEST_SOURCE_PROJECT,
    RELATED_SESSION_DIGEST_SOURCE_EXTERNAL,
)

SESSION_SUMMARY_KIND_WORKING_MEMORY = "working_memory"
SESSION_SUMMARY_KIND_SESSION_DIGEST = "session_digest"
SESSION_SUMMARY_KINDS = (
    SESSION_SUMMARY_KIND_WORKING_MEMORY,
    SESSION_SUMMARY_KIND_SESSION_DIGEST,
)

ProjectAccessMode = Literal["open", "project_only"]
RecordStatus = Literal["active", "archived"]
SessionVisibilityMode = Literal["shared", "private"]
RelatedSessionDigestSourceScope = Literal["project", "external"]
SessionSummaryKind = Literal["working_memory", "session_digest"]
