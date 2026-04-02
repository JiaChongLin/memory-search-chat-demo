import {
  getAccessModeHelpText,
  getAccessModeLabel,
  getCurrentProjectAccessLabel,
  getDebugFieldLabel,
  getBoolLabel,
  getFallbackReasonLabel,
  getDerivedMemoryStatusLabel,
  getModelUsageLabel,
  getPrivacyHelpText,
  getPrivacyLabel,
  getRoleLabel,
  getSearchUsageLabel,
  getSessionTitle,
  getStatusLabel,
} from "./labels.js";
import {
  getDebugForSession,
  getMemoryForSession,
  getMessagesForCurrentSession,
} from "./state.js";

const messageRenderCache = {
  sessionId: null,
  messagesRef: null,
  messageCount: 0,
  lastMessageKey: "",
  emptyStateKey: "",
};

function formatTime(timestamp) {
  if (!timestamp) {
    return "";
  }

  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function buildDebugItems(message) {
  if (message.role !== "assistant" || !message.debug) {
    return [];
  }

  const debug = message.debug;
  const items = [
    { label: `解析结果：${getAccessModeLabel(debug.context_scope || "open")}`, variant: "scope" },
    { label: `关联 session_digest ${debug.related_session_digest_count ?? 0}`, variant: "soft" },
    {
      label: getModelUsageLabel(debug.used_live_model),
      variant: debug.used_live_model ? "success" : "warning",
    },
  ];

  if (debug.search_triggered || debug.search_used) {
    items.push({
      label: getSearchUsageLabel(debug.search_triggered, debug.search_used),
      variant: "info",
    });
  }

  if (debug.fallback_reason) {
    items.push({
      label: `降级原因：${getFallbackReasonLabel(debug.fallback_reason)}`,
      variant: "danger",
    });
  }

  return items;
}

function resolveCurrentProject(state) {
  const session = state.selectedSessionDetail;
  if (!session?.project_id) {
    return null;
  }

  return state.projects.find((item) => item.id === session.project_id) || null;
}

function renderHeader(state, elements) {
  const session = state.selectedSessionDetail;
  const project = resolveCurrentProject(state);

  if (!session) {
    elements.currentSessionLabel.textContent = "请选择一个会话";
    elements.currentProjectLabel.className = "badge soft";
    elements.currentProjectLabel.textContent = "无项目";
    elements.currentVisibilityBadge.className = "badge neutral";
    elements.currentVisibilityBadge.textContent = "未选择";
    elements.currentStatusBadge.className = "badge neutral";
    elements.currentStatusBadge.textContent = "未选择";
    elements.selectionHint.textContent =
      "请先从左侧导航中创建或选择一个会话，然后在这里继续聊天。";
    if (elements.renameSessionButton) {
      elements.renameSessionButton.disabled = true;
    }
    return;
  }

  elements.currentSessionLabel.textContent = getSessionTitle(session.title);
  elements.currentProjectLabel.className = `badge ${project ? "scope" : "soft"}`;
  elements.currentProjectLabel.textContent = project
    ? `${project.name} · ${getAccessModeLabel(project.access_mode)}`
    : "无项目会话";
  elements.currentVisibilityBadge.className = `badge ${session.is_private ? "danger" : "soft"}`;
  elements.currentVisibilityBadge.textContent = getPrivacyLabel(session.is_private);
  elements.currentStatusBadge.className = `badge ${
    session.status === "active" ? "success" : "warning"
  }`;
  elements.currentStatusBadge.textContent = getStatusLabel(session.status);
  if (elements.renameSessionButton) {
    elements.renameSessionButton.disabled = false;
  }

  if (session.status === "archived") {
    elements.selectionHint.textContent =
      "当前会话已归档。你仍然可以查看历史和调试信息，但聊天输入区会保持禁用。";
    return;
  }

  const baseHint = project
    ? `当前项目为 ${getAccessModeLabel(project.access_mode)}，${getAccessModeHelpText(project.access_mode)}`
    : "当前会话不属于任何项目，会按开放可访问历史来解析可读上下文。";
  elements.selectionHint.textContent = `${baseHint} ${getPrivacyHelpText(session.is_private)}`;
}

function renderDebugPanel(state, elements) {
  const sessionId = state.currentSessionId;
  const debug = getDebugForSession(sessionId);
  const memory = getMemoryForSession(sessionId);
  const session = state.selectedSessionDetail;
  const project = resolveCurrentProject(state);

  const rows = [
    ["session_id", sessionId || "未选择"],
    ["current_project_access", getCurrentProjectAccessLabel(project)],
    ["current_session_visibility", session ? getPrivacyLabel(session.is_private) : "未选择"],
    ["context_scope", getAccessModeLabel(debug?.context_scope)],
    ["related_session_digest_count", String(debug?.related_session_digest_count ?? 0)],
    ["used_live_model", getBoolLabel(debug?.used_live_model)],
    ["fallback_reason", getFallbackReasonLabel(debug?.fallback_reason)],
    ["search_triggered", getBoolLabel(debug?.search_triggered)],
    ["search_used", getBoolLabel(debug?.search_used)],
    ["working_memory_state", getDerivedMemoryStatusLabel(Boolean(memory?.working_memory))],
    ["session_digest_state", getDerivedMemoryStatusLabel(Boolean(memory?.session_digest))],
  ];

  elements.debugInfo.innerHTML = rows
    .map(
      ([key, value]) => `
        <div class="debug-item">
          <dt>${getDebugFieldLabel(key)}</dt>
          <dd>${value}</dd>
        </div>
      `,
    )
    .join("");

  const notes = [];
  if (project) {
    notes.push(`当前项目：${getAccessModeHelpText(project.access_mode)}`);
  } else if (session) {
    notes.push("当前会话不属于任何项目，因此按开放可访问历史解释项目边界。");
  }
  if (session) {
    notes.push(`当前会话：${getPrivacyHelpText(session.is_private)}`);
  }
  if (!debug && sessionId) {
    notes.push("调试快照只在当前页面会话内保留；刷新后不会从后端恢复。");
  }

  elements.debugNote.textContent = notes.length
    ? notes.join(" ")
    : "这里会继续显示 context_scope，但现在按 access_mode 语义解释，而不是旧的四档 scope。";
}

function renderMemoryField(textElement, badgeElement, value, emptyText) {
  if (value) {
    textElement.textContent = value;
    badgeElement.className = "badge success";
    badgeElement.textContent = "已缓存";
    return;
  }

  textElement.textContent = emptyText;
  badgeElement.className = "badge neutral";
  badgeElement.textContent = "暂无";
}

function renderMemory(state, elements) {
  const memory = getMemoryForSession(state.currentSessionId);
  const hasSession = Boolean(state.currentSessionId);

  renderMemoryField(
    elements.workingMemoryText,
    elements.workingMemoryBadge,
    memory?.working_memory || null,
    hasSession
      ? "\u5f53\u524d\u8fd8\u6ca1\u6709 working_memory\uff08\u8fd0\u884c\u65f6\u8854\u63a5\u8bb0\u5fc6\uff09\u3002\u5b83\u7528\u4e8e\u5ef6\u7eed\u5f53\u524d\u4f1a\u8bdd\uff0c\u4e0d\u7b49\u4e8e\u6d88\u606f\u5386\u53f2\u3002"
      : "当前没有选中会话。请先在左侧导航中创建或选择会话。",
  );

  renderMemoryField(
    elements.sessionDigestText,
    elements.sessionDigestBadge,
    memory?.session_digest || null,
    hasSession
      ? "\u5f53\u524d\u8fd8\u6ca1\u6709 session_digest\uff08\u8de8\u4f1a\u8bdd\u6458\u8981\uff09\u3002\u5b83\u7528\u4e8e\u8de8\u4f1a\u8bdd\u5f15\u7528\uff0c\u4e0d\u7b49\u4e8e\u6d88\u606f\u5386\u53f2\u3002"
      : "当前没有选中会话。请先在左侧导航中创建或选择会话。",
  );
}

function renderComposerState(state, elements) {
  const session = state.selectedSessionDetail;
  const missingSelection = !session;
  const locked = session?.status === "archived";
  const disabled = state.busy.chat || missingSelection || locked;

  elements.sendButton.disabled = disabled;
  elements.messageInput.disabled = disabled;

  if (state.busy.chat) {
    elements.composerHint.textContent = "请求进行中，请稍候...";
    return;
  }

  if (missingSelection) {
    elements.composerHint.textContent = "请先从左侧导航中选择一个会话。";
    elements.messageInput.placeholder = "先在左侧选中会话，再开始聊天。";
    return;
  }

  if (locked) {
    elements.composerHint.textContent = "当前会话已归档，输入区保持禁用。";
    elements.messageInput.placeholder = "请切换到其他会话，或创建一个新聊天继续测试。";
    return;
  }

  elements.composerHint.textContent = "Shift + Enter 换行，Enter 发送。";
  elements.messageInput.placeholder = "\u7ee7\u7eed\u5f53\u524d\u4f1a\u8bdd\uff0c\u89c2\u5bdf working_memory\u3001session_digest\u3001sources \u548c debug \u5b57\u6bb5\u53d8\u5316\u3002";
}

function renderNotice(state, elements) {
  const notice = state.notices.chat;
  if (!notice?.message) {
    elements.chatNotice.className = "notice hidden";
    elements.chatNotice.textContent = "";
    return;
  }

  elements.chatNotice.className = `notice ${notice.variant || "info"}`;
  elements.chatNotice.textContent = notice.message;
}

function resolveSafeSourceHref(rawUrl) {
  if (!rawUrl) {
    return null;
  }

  try {
    const parsed = new URL(rawUrl, window.location.origin);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.toString();
    }
  } catch {
    return null;
  }

  return null;
}

function buildSourceNode(source) {
  const link = document.createElement("a");
  link.className = "source-card";

  const title = document.createElement("strong");
  title.textContent = source?.title || "";

  const snippet = document.createElement("span");
  snippet.textContent = source?.snippet || source?.url || "";

  link.append(title, snippet);

  const rawUrl = typeof source?.url === "string" ? source.url.trim() : "";
  const safeHref = resolveSafeSourceHref(rawUrl);
  if (safeHref) {
    link.href = safeHref;
    link.target = "_blank";
    link.rel = "noreferrer";
    return link;
  }

  link.setAttribute("aria-disabled", "true");
  link.tabIndex = -1;
  return link;
}

function buildMessageNode(message, template) {
  const node = template.content.firstElementChild.cloneNode(true);
  node.classList.add(`message-${message.role}`);

  node.querySelector(".message-role").textContent = getRoleLabel(message.role);
  node.querySelector(".message-time").textContent = formatTime(message.timestamp);
  node.querySelector(".message-content").textContent = message.content;

  const metaContainer = node.querySelector(".message-meta");
  const metaItems = buildDebugItems(message);
  if (metaItems.length === 0) {
    metaContainer.remove();
  } else {
    metaContainer.innerHTML = metaItems
      .map((item) => `<span class="badge ${item.variant}">${item.label}</span>`)
      .join("");
  }

  const sourceList = node.querySelector(".source-list");
  if (!Array.isArray(message.sources) || message.sources.length === 0) {
    sourceList.remove();
  } else {
    message.sources.forEach((source) => {
      sourceList.appendChild(buildSourceNode(source));
    });
  }

  return node;
}

function getMessageKey(message) {
  return [
    message?.role || "",
    String(message?.timestamp || ""),
    message?.content || "",
    String(Array.isArray(message?.sources) ? message.sources.length : 0),
    String(message?.debug?.related_session_digest_count ?? message?.debug?.related_summary_count ?? ""),
  ].join("|");
}

function updateMessageRenderCache(sessionId, messages) {
  messageRenderCache.sessionId = sessionId;
  messageRenderCache.messagesRef = messages;
  messageRenderCache.messageCount = messages.length;
  messageRenderCache.lastMessageKey = messages.length
    ? getMessageKey(messages[messages.length - 1])
    : "";
  messageRenderCache.emptyStateKey = sessionId ? "empty-session" : "empty-selection";
}

function renderEmptyState(state, elements) {
  const sessionId = state.currentSessionId || null;
  const emptyStateKey = sessionId ? "empty-session" : "empty-selection";
  const needsUpdate =
    messageRenderCache.sessionId !== sessionId ||
    messageRenderCache.messageCount !== 0 ||
    messageRenderCache.emptyStateKey !== emptyStateKey;

  if (!needsUpdate) {
    return;
  }

  elements.messageList.innerHTML = "";
  elements.chatEmptyState.hidden = false;
  elements.chatEmptyState.innerHTML = sessionId
    ? `
        <div>
          <strong>这个会话还没有消息</strong>
          <span>从这里发出第一条消息，或继续把它当作一个新的讨论起点。</span>
        </div>
      `
    : `
        <div>
          <strong>请选择一个会话开始</strong>
          <span>左侧导航会按项目和未归属会话组织列表。选中会话后，右侧会切换到对应聊天主区。</span>
        </div>
      `;
  updateMessageRenderCache(sessionId, []);
}

function renderMessages(state, elements) {
  const sessionId = state.currentSessionId || null;
  const messages = sessionId ? getMessagesForCurrentSession() : [];

  if (!messages.length) {
    renderEmptyState(state, elements);
    return;
  }

  const lastMessageKey = getMessageKey(messages[messages.length - 1]);
  const sameSession = messageRenderCache.sessionId === sessionId;
  const sameArrayRef = messageRenderCache.messagesRef === messages;
  const sameTail =
    messageRenderCache.messageCount === messages.length &&
    messageRenderCache.lastMessageKey === lastMessageKey;

  if (sameSession && sameArrayRef && sameTail) {
    return;
  }

  elements.chatEmptyState.hidden = true;
  elements.chatEmptyState.innerHTML = "";

  const canAppendOnly =
    sameSession &&
    sameArrayRef &&
    messages.length > messageRenderCache.messageCount &&
    elements.messageList.childElementCount === messageRenderCache.messageCount;

  if (canAppendOnly) {
    for (let index = messageRenderCache.messageCount; index < messages.length; index += 1) {
      elements.messageList.appendChild(buildMessageNode(messages[index], elements.messageTemplate));
    }
    updateMessageRenderCache(sessionId, messages);
    elements.messageList.scrollTop = elements.messageList.scrollHeight;
    return;
  }

  elements.messageList.innerHTML = "";
  messages.forEach((message) => {
    elements.messageList.appendChild(buildMessageNode(message, elements.messageTemplate));
  });
  updateMessageRenderCache(sessionId, messages);
  elements.messageList.scrollTop = elements.messageList.scrollHeight;
}

export function renderChat(state, elements) {
  renderNotice(state, elements);
  renderHeader(state, elements);
  renderMemory(state, elements);
  renderDebugPanel(state, elements);
  renderComposerState(state, elements);
  renderMessages(state, elements);
}

