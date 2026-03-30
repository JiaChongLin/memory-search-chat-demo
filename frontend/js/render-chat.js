import {
  getAccessModeHelpText,
  getAccessModeLabel,
  getCurrentProjectAccessLabel,
  getDebugFieldLabel,
  getBoolLabel,
  getFallbackReasonLabel,
  getModelUsageLabel,
  getPrivacyHelpText,
  getPrivacyLabel,
  getRoleLabel,
  getSearchUsageLabel,
  getSessionTitle,
  getStatusLabel,
  getSummaryCachedLabel,
} from "./labels.js";
import {
  getDebugForSession,
  getMessagesForCurrentSession,
  getSummaryForSession,
} from "./state.js";

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
    { label: `相关摘要 ${debug.related_summary_count ?? 0} 条`, variant: "soft" },
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
      "请从左侧导航中创建或选择一个会话，然后在这里继续聊天。";
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

  if (session.status === "archived") {
    elements.selectionHint.textContent =
      "当前会话已归档。你仍可以查看历史和调试信息，但聊天输入区会保持禁用。";
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
  const summary = getSummaryForSession(sessionId);
  const session = state.selectedSessionDetail;
  const project = resolveCurrentProject(state);

  const rows = [
    ["session_id", sessionId || "未选择"],
    ["current_project_access", getCurrentProjectAccessLabel(project)],
    ["current_session_visibility", session ? getPrivacyLabel(session.is_private) : "未选择"],
    ["context_scope", getAccessModeLabel(debug?.context_scope)],
    ["related_summary_count", String(debug?.related_summary_count ?? 0)],
    ["used_live_model", getBoolLabel(debug?.used_live_model)],
    ["fallback_reason", getFallbackReasonLabel(debug?.fallback_reason)],
    ["search_triggered", getBoolLabel(debug?.search_triggered)],
    ["search_used", getBoolLabel(debug?.search_used)],
    ["summary_cached", getSummaryCachedLabel(Boolean(summary))],
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

  elements.debugInfo.dataset.notes = notes.join(" ");
  elements.debugNote.textContent = notes.length
    ? notes.join(" ")
    : "这里会继续显示 context_scope，但按当前 access_mode 语义解释，而不是旧四档 scope。";
}

function renderSummary(state, elements) {
  const summary = getSummaryForSession(state.currentSessionId);
  if (summary) {
    elements.summaryText.textContent = summary;
    elements.summaryBadge.className = "badge success";
    elements.summaryBadge.textContent = "已缓存";
    return;
  }

  elements.summaryText.textContent = state.currentSessionId
    ? "当前选中会话还没有本地缓存 summary。只有本页内完成的聊天请求会更新这里的摘要展示。"
    : "当前没有选中会话。请先在左侧导航中创建或选择会话。";
  elements.summaryBadge.className = "badge neutral";
  elements.summaryBadge.textContent = "无摘要";
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
  elements.messageInput.placeholder = "围绕当前会话继续聊天，观察 summary、sources 和调试信息变化。";
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
    sourceList.innerHTML = message.sources
      .map(
        (source) => `
          <a class="source-card" href="${source.url}" target="_blank" rel="noreferrer">
            <strong>${source.title}</strong>
            <span>${source.snippet || source.url}</span>
          </a>
        `,
      )
      .join("");
  }

  return node;
}

function renderMessages(state, elements) {
  const messages = state.currentSessionId ? getMessagesForCurrentSession() : [];
  elements.messageList.innerHTML = "";

  if (!messages.length) {
    elements.chatEmptyState.hidden = false;
    elements.chatEmptyState.innerHTML = state.currentSessionId
      ? `
        <div>
          <strong>这个会话还没有本地渲染消息</strong>
          <span>当前前端只展示本页面会话期间缓存过的消息。发送一条新消息后，这里会变成聊天主区。</span>
        </div>
      `
      : `
        <div>
          <strong>请选择一个会话开始</strong>
          <span>左侧导航会按项目和未归属会话组织列表。选中会话后，右侧会切换到对应聊天主区。</span>
        </div>
      `;
    return;
  }

  elements.chatEmptyState.hidden = true;
  messages.forEach((message) => {
    elements.messageList.appendChild(buildMessageNode(message, elements.messageTemplate));
  });
  elements.messageList.scrollTop = elements.messageList.scrollHeight;
}

export function renderChat(state, elements) {
  renderNotice(state, elements);
  renderHeader(state, elements);
  renderSummary(state, elements);
  renderDebugPanel(state, elements);
  renderComposerState(state, elements);
  renderMessages(state, elements);
}
