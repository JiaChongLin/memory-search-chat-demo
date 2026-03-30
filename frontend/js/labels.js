const ACCESS_MODE_LABELS = {
  open: "开放项目",
  project_only: "仅限项目",
};

const STATUS_LABELS = {
  active: "启用中",
  archived: "已归档",
  deleted: "已删除",
};

const DEBUG_FIELD_LABELS = {
  session_id: "会话 ID",
  current_project_access: "当前项目访问模式",
  current_session_visibility: "当前会话可见性",
  context_scope: "解析结果",
  related_summary_count: "相关摘要数",
  used_live_model: "是否直连模型",
  fallback_reason: "降级原因",
  search_triggered: "是否触发搜索",
  search_used: "是否使用搜索结果",
  summary_cached: "本地摘要缓存",
};

const FALLBACK_REASON_LABELS = {
  missing_api_key: "缺少 API Key",
  live_model_disabled: "已关闭在线模型",
  provider_request_failed: "在线模型请求失败",
};

export function getAccessModeLabel(value) {
  return ACCESS_MODE_LABELS[value] || value || "未知";
}

export function getAccessModeHelpText(value) {
  if (value === "project_only") {
    return "只能访问项目内历史，项目内会话对项目外不可见。";
  }
  if (value === "open") {
    return "可访问外部可访问历史，且自身非私密会话也可被外部访问。";
  }
  return "未识别访问模式。";
}

export function getStatusLabel(value) {
  return STATUS_LABELS[value] || value || "未知";
}

export function getPrivacyLabel(isPrivate) {
  return isPrivate ? "私密会话" : "共享会话";
}

export function getPrivacyHelpText(isPrivate) {
  return isPrivate
    ? "不会被其他会话访问，但自己仍然可以访问其他允许访问的历史。"
    : "可被其他允许访问的会话读取，也可以读取其他允许访问的历史。";
}

export function getProjectBindingLabel(projectId) {
  return projectId ? "已归属项目" : "无项目会话";
}

export function getProjectIdLabel(projectId) {
  return projectId ? `项目 #${projectId}` : "无项目";
}

export function getCurrentProjectAccessLabel(project) {
  if (!project) {
    return "无项目，按开放历史处理";
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
  return value ? "是" : "否";
}

export function getSummaryCachedLabel(hasSummary) {
  return hasSummary ? "已缓存" : "未缓存";
}

export function getModelUsageLabel(usedLiveModel) {
  return usedLiveModel ? "在线模型" : "降级回复";
}

export function getSearchUsageLabel(searchTriggered, searchUsed) {
  if (searchUsed) {
    return "已使用搜索";
  }
  if (searchTriggered) {
    return "已触发搜索";
  }
  return "未触发搜索";
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
    return "用户";
  }
  if (role === "assistant") {
    return "助手";
  }
  return "系统";
}

export function getSessionTitle(title) {
  return title || "未命名会话";
}
