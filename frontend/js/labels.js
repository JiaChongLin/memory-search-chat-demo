const ACCESS_MODE_LABELS = {
  open: "\u5f00\u653e\u9879\u76ee",
  project_only: "\u4ec5\u9650\u9879\u76ee",
};

const STATUS_LABELS = {
  active: "\u6d3b\u8dc3\u4e2d",
  archived: "\u5df2\u5f52\u6863",
};

const DEBUG_FIELD_LABELS = {
  session_id: "\u4f1a\u8bdd ID",
  current_project_access: "\u5f53\u524d\u9879\u76ee\u8bbf\u95ee\u6a21\u5f0f",
  current_session_visibility: "\u5f53\u524d\u4f1a\u8bdd\u53ef\u89c1\u6027",
  context_scope: "\u4e0a\u4e0b\u6587\u8bbf\u95ee\u8303\u56f4",
  related_session_digest_count: "\u5173\u8054 session_digest \u6570\u91cf",
  used_live_model: "\u662f\u5426\u4f7f\u7528\u5728\u7ebf\u6a21\u578b",
  fallback_reason: "\u56de\u9000\u539f\u56e0",
  search_triggered: "\u662f\u5426\u89e6\u53d1\u641c\u7d22",
  search_used: "\u662f\u5426\u4f7f\u7528\u641c\u7d22\u7ed3\u679c",
  working_memory_state: "working_memory \u72b6\u6001",
  session_digest_state: "session_digest \u72b6\u6001",
};

const FALLBACK_REASON_LABELS = {
  missing_api_key: "\u7f3a\u5c11 API Key",
  live_model_disabled: "\u5728\u7ebf\u6a21\u578b\u5df2\u7981\u7528",
  provider_request_failed: "\u5728\u7ebf\u6a21\u578b\u8bf7\u6c42\u5931\u8d25",
};

export function getAccessModeLabel(value) {
  return ACCESS_MODE_LABELS[value] || value || "\u672a\u77e5";
}

export function getAccessModeHelpText(value) {
  if (value === "project_only") {
    return "\u53ea\u80fd\u8bfb\u53d6\u540c\u4e00\u9879\u76ee\u5185\u7684\u5386\u53f2\uff0c\u9879\u76ee\u5185\u4f1a\u8bdd\u4e5f\u4e0d\u4f1a\u88ab\u9879\u76ee\u5916\u8bbf\u95ee\u3002";
  }
  if (value === "open") {
    return "\u53ef\u4ee5\u8bfb\u53d6\u5bf9\u5916\u53ef\u89c1\u7684\u5386\u53f2\uff0c\u9879\u76ee\u4e2d\u7684\u975e\u79c1\u5bc6\u4f1a\u8bdd\u4e5f\u53ef\u4ee5\u88ab\u9879\u76ee\u5916\u8bbf\u95ee\u3002";
  }
  return "\u672a\u77e5\u8bbf\u95ee\u6a21\u5f0f\u3002";
}

export function getStatusLabel(value) {
  return STATUS_LABELS[value] || value || "\u672a\u77e5";
}

export function getPrivacyLabel(isPrivate) {
  return isPrivate ? "\u79c1\u5bc6\u4f1a\u8bdd" : "\u5171\u4eab\u4f1a\u8bdd";
}

export function getPrivacyHelpText(isPrivate) {
  return isPrivate
    ? "\u5f53\u524d\u4f1a\u8bdd\u4e0d\u4f1a\u88ab\u5176\u4ed6\u4f1a\u8bdd\u8bfb\u53d6\uff0c\u4f46\u4ecd\u7136\u53ef\u4ee5\u8bfb\u53d6\u81ea\u5df1\u6709\u6743\u9650\u8bbf\u95ee\u7684\u5386\u53f2\u3002"
    : "\u5f53\u524d\u4f1a\u8bdd\u53ef\u4ee5\u88ab\u5176\u4ed6\u6709\u6743\u9650\u7684\u4f1a\u8bdd\u8bfb\u53d6\uff0c\u4e5f\u53ef\u4ee5\u8bfb\u53d6\u81ea\u5df1\u6709\u6743\u9650\u8bbf\u95ee\u7684\u5386\u53f2\u3002";
}

export function getCurrentProjectAccessLabel(project) {
  if (!project) {
    return "\u65e0\u9879\u76ee\uff0c\u6309\u5f00\u653e\u5386\u53f2\u5904\u7406";
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
  return value ? "\u662f" : "\u5426";
}

export function getDerivedMemoryStatusLabel(hasValue) {
  return hasValue ? "\u5df2\u751f\u6210" : "\u672a\u751f\u6210";
}

export function getModelUsageLabel(usedLiveModel) {
  return usedLiveModel ? "\u4f7f\u7528\u5728\u7ebf\u6a21\u578b" : "\u4f7f\u7528\u56de\u9000\u56de\u590d";
}

export function getSearchUsageLabel(searchTriggered, searchUsed) {
  if (searchUsed) {
    return "\u5df2\u4f7f\u7528\u641c\u7d22\u7ed3\u679c";
  }
  if (searchTriggered) {
    return "\u5df2\u89e6\u53d1\u641c\u7d22";
  }
  return "\u672a\u89e6\u53d1\u641c\u7d22";
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
    return "\u7528\u6237";
  }
  if (role === "assistant") {
    return "\u52a9\u624b";
  }
  return "\u7cfb\u7edf";
}

export function getSessionTitle(title) {
  return title || "\u672a\u547d\u540d\u4f1a\u8bdd";
}
