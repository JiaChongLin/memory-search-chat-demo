const ACCESS_MODE_LABELS = {
  open: "Open project",
  project_only: "Project only",
};

const STATUS_LABELS = {
  active: "Active",
  archived: "Archived",
};

const DEBUG_FIELD_LABELS = {
  session_id: "Session ID",
  current_project_access: "Current project access",
  current_session_visibility: "Current session visibility",
  context_scope: "Context scope",
  related_session_digest_count: "Related session_digest count",
  used_live_model: "Live model used",
  fallback_reason: "Fallback reason",
  search_triggered: "Search triggered",
  search_used: "Search results used",
  working_memory_state: "working_memory state",
  session_digest_state: "session_digest state",
};

const FALLBACK_REASON_LABELS = {
  missing_api_key: "Missing API key",
  live_model_disabled: "Live model disabled",
  provider_request_failed: "Live model request failed",
};

export function getAccessModeLabel(value) {
  return ACCESS_MODE_LABELS[value] || value || "Unknown";
}

export function getAccessModeHelpText(value) {
  if (value === "project_only") {
    return "Can only read history from the same project, and project sessions stay invisible outside the project.";
  }
  if (value === "open") {
    return "Can read externally visible history, and non-private sessions in this project can also be read from outside.";
  }
  return "Unknown access mode.";
}

export function getStatusLabel(value) {
  return STATUS_LABELS[value] || value || "Unknown";
}

export function getPrivacyLabel(isPrivate) {
  return isPrivate ? "Private session" : "Shared session";
}

export function getPrivacyHelpText(isPrivate) {
  return isPrivate
    ? "This session cannot be read by other sessions, but it can still read other allowed history."
    : "This session can be read by other allowed sessions and can also read other allowed history.";
}

export function getCurrentProjectAccessLabel(project) {
  if (!project) {
    return "No project; treat as open history.";
  }
  return getAccessModeLabel(project.access_mode);
}

export function getDebugFieldLabel(key) {
  return DEBUG_FIELD_LABELS[key] || key;
}

export function getBoolLabel(value) {
  if (value === undefined || value === null) {
    return "-";
  }
  return value ? "Yes" : "No";
}

export function getDerivedMemoryStatusLabel(hasValue) {
  return hasValue ? "Generated" : "Not generated";
}

export function getModelUsageLabel(usedLiveModel) {
  return usedLiveModel ? "Live model" : "Fallback reply";
}

export function getSearchUsageLabel(searchTriggered, searchUsed) {
  if (searchUsed) {
    return "Search results used";
  }
  if (searchTriggered) {
    return "Search triggered";
  }
  return "Search not triggered";
}

export function getFallbackReasonLabel(reason) {
  if (!reason) {
    return "-";
  }

  for (const [prefix, label] of Object.entries(FALLBACK_REASON_LABELS)) {
    if (reason.startsWith(prefix)) {
      return label;
    }
  }

  return reason;
}

export function getRoleLabel(role) {
  if (role === "user") {
    return "User";
  }
  if (role === "assistant") {
    return "Assistant";
  }
  return "System";
}

export function getSessionTitle(title) {
  return title || "Untitled session";
}
