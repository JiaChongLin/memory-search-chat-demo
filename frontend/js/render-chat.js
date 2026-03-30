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
    { label: debug.context_scope || "conversation_only", variant: "scope" },
    { label: `related: ${debug.related_summary_count ?? 0}`, variant: "soft" },
    {
      label: debug.used_live_model ? "live model" : "fallback",
      variant: debug.used_live_model ? "success" : "warning",
    },
  ];

  if (debug.search_triggered) {
    items.push({
      label: debug.search_used ? "search used" : "search triggered",
      variant: "info",
    });
  }

  if (debug.fallback_reason) {
    items.push({ label: `reason: ${debug.fallback_reason}`, variant: "danger" });
  }

  return items;
}

function renderDebugPanel(state, elements) {
  const sessionId = state.currentSessionId;
  const debug = getDebugForSession(sessionId);
  const summary = getSummaryForSession(sessionId);

  const rows = [
    ["session_id", sessionId || "未选中"],
    ["context_scope", debug?.context_scope || "-"],
    ["related_summary_count", String(debug?.related_summary_count ?? 0)],
    ["used_live_model", debug?.used_live_model === undefined ? "-" : String(debug.used_live_model)],
    ["fallback_reason", debug?.fallback_reason || "-"],
    ["search_triggered", debug?.search_triggered === undefined ? "-" : String(debug.search_triggered)],
    ["search_used", debug?.search_used === undefined ? "-" : String(debug.search_used)],
    ["summary_cached", summary ? "yes" : "no"],
  ];

  elements.debugInfo.innerHTML = rows
    .map(
      ([key, value]) => `
        <div class="debug-item">
          <dt>${key}</dt>
          <dd>${value}</dd>
        </div>
      `,
    )
    .join("");
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
    ? "当前选中会话还没有本地缓存摘要。只有本页面发起的聊天响应会更新这里的摘要显示。"
    : "当前没有选中会话。请先在中间栏创建或选择会话，然后再到右侧聊天区发消息。";
  elements.summaryBadge.className = "badge neutral";
  elements.summaryBadge.textContent = "无摘要";
}

function renderComposerState(state, elements) {
  const session = state.selectedSessionDetail;
  const missingSelection = !session;
  const locked = ["archived", "deleted"].includes(session?.status);
  const disabled = state.busy.chat || missingSelection || locked;

  elements.sendButton.disabled = disabled;
  elements.messageInput.disabled = disabled;

  if (state.busy.chat) {
    elements.composerHint.textContent = "请求进行中，等待后端响应...";
    return;
  }

  if (missingSelection) {
    elements.composerHint.textContent = "请先在中间栏创建或选择一个会话，然后才能发送消息。";
    return;
  }

  if (locked) {
    elements.composerHint.textContent = "当前会话已归档或删除。请切换到其他会话，或创建新会话继续测试。";
    return;
  }

  elements.composerHint.textContent = "Shift + Enter 换行，Enter 发送。";
}

function renderSelectionHint(state, elements) {
  const session = state.selectedSessionDetail;
  if (!session) {
    elements.selectionHint.textContent = "请先在中间栏显式选择或创建会话。当前未选中 session 时，右侧聊天区不会直接发送消息。";
    return;
  }

  const projectLabel = session.project_id ? `项目 #${session.project_id}` : "无项目";
  elements.selectionHint.textContent = `当前会话：${session.title || "Untitled Session"}，归属：${projectLabel}，状态：${session.status}。`;
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

  node.querySelector(".message-role").textContent =
    message.role === "user" ? "User" : message.role === "assistant" ? "Assistant" : "System";
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
    elements.chatEmptyState.textContent = state.currentSessionId
      ? "当前会话没有本地渲染过的消息。后端没有提供完整消息查询接口，所以这里只显示本页面期间缓存过的消息。"
      : "当前未选中会话。请先在中间栏选择已有会话，或先创建一个空白会话。";
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
  renderSummary(state, elements);
  renderDebugPanel(state, elements);
  renderSelectionHint(state, elements);
  renderComposerState(state, elements);
  renderMessages(state, elements);

  if (!state.currentSessionId) {
    elements.currentSessionLabel.textContent = "未选中";
  }
}
