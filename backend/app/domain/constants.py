from __future__ import annotations

from typing import Literal


SCOPE_MODE_CONVERSATION_ONLY = "conversation_only"
SCOPE_MODE_PROJECT_ONLY = "project_only"
SCOPE_MODE_PROJECT_PLUS_GLOBAL = "project_plus_global"
SCOPE_MODE_GLOBAL = "global"
PROJECT_SCOPE_MODES = (
    SCOPE_MODE_CONVERSATION_ONLY,
    SCOPE_MODE_PROJECT_ONLY,
    SCOPE_MODE_PROJECT_PLUS_GLOBAL,
    SCOPE_MODE_GLOBAL,
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
RELATED_SUMMARY_SOURCE_GLOBAL = "global"
RELATED_SUMMARY_SOURCE_SCOPES = (
    RELATED_SUMMARY_SOURCE_PROJECT,
    RELATED_SUMMARY_SOURCE_GLOBAL,
)

ProjectScopeMode = Literal[
    "conversation_only",
    "project_only",
    "project_plus_global",
    "global",
]
RecordStatus = Literal["active", "archived", "deleted"]
RelatedSummarySourceScope = Literal["project", "global"]
