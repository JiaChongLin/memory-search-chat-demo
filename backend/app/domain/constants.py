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
STATUS_DELETED = "deleted"
RECORD_STATUSES = (
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    STATUS_DELETED,
)

RELATED_SUMMARY_SOURCE_PROJECT = "project"
RELATED_SUMMARY_SOURCE_EXTERNAL = "external"
RELATED_SUMMARY_SOURCE_SCOPES = (
    RELATED_SUMMARY_SOURCE_PROJECT,
    RELATED_SUMMARY_SOURCE_EXTERNAL,
)

ProjectAccessMode = Literal["open", "project_only"]
RecordStatus = Literal["active", "archived", "deleted"]
SessionVisibilityMode = Literal["shared", "private"]
RelatedSummarySourceScope = Literal["project", "external"]
