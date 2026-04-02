export const COMPOSER_MIN_HEIGHT = 52;
export const COMPOSER_MAX_HEIGHT = 188;

export function formatErrorMessage(error) {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "\u672a\u77e5\u9519\u8bef";
}

export function parseOptionalProjectId(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  if (value === "__none__") {
    return null;
  }
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? null : parsed;
}

export function buildAssistantDebug(responseData) {
  const relatedSessionDigestCount =
    responseData.related_session_digest_count ?? responseData.related_summary_count ?? 0;

  return {
    session_id: responseData.session_id,
    context_scope: responseData.context_scope,
    related_session_digest_count: relatedSessionDigestCount,
    used_live_model: responseData.used_live_model,
    fallback_reason: responseData.fallback_reason,
    search_triggered: responseData.search_triggered,
    search_used: responseData.search_used,
  };
}

function mapApiSource(source) {
  if (!source || typeof source !== "object") {
    return null;
  }

  const title = typeof source.title === "string" ? source.title : "";
  const url = typeof source.url === "string" ? source.url : "";
  if (!title || !url) {
    return null;
  }

  return {
    title,
    url,
    snippet: typeof source.snippet === "string" ? source.snippet : null,
  };
}

export function mapApiMessage(message) {
  const rawSources = Array.isArray(message.sources) ? message.sources : [];
  const sources = rawSources.map((source) => mapApiSource(source)).filter(Boolean);

  return {
    role: message.role,
    content: message.content,
    timestamp: message.created_at,
    sources,
  };
}

export function resizeComposer(elements) {
  const textarea = elements.messageInput;
  if (!textarea) {
    return;
  }

  textarea.style.height = `${COMPOSER_MIN_HEIGHT}px`;
  const nextHeight = Math.min(textarea.scrollHeight, COMPOSER_MAX_HEIGHT);
  textarea.style.height = `${Math.max(COMPOSER_MIN_HEIGHT, nextHeight)}px`;
  textarea.style.overflowY = textarea.scrollHeight > COMPOSER_MAX_HEIGHT ? "auto" : "hidden";
}

export function resetComposer(elements) {
  const textarea = elements.messageInput;
  if (!textarea) {
    return;
  }

  textarea.value = "";
  textarea.style.height = `${COMPOSER_MIN_HEIGHT}px`;
  textarea.style.overflowY = "hidden";
}

export function resetProjectForm(elements) {
  elements.projectForm.reset();
  elements.projectAccessSelect.value = "open";
}
