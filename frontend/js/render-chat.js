import {
  getAccessModeHelpText,
  getAccessModeLabel,
  getBoolLabel,
  getCurrentProjectAccessLabel,
  getDebugFieldLabel,
  getDerivedMemoryStatusLabel,
  getFallbackReasonLabel,
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
import { getLatestTurnIndexes } from "./helpers/ui-helpers.js";

const messageRenderCache = {
  sessionId: null,
  messagesRef: null,
  messageCount: 0,
  lastMessageKey: "",
  emptyStateKey: "",
  latestUserIndex: -1,
  latestAssistantIndex: -1,
  sessionStatusKey: "",
  editStateKey: "",
  editingMessageIndex: -1,
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
    {
      label: `解析结果：${getAccessModeLabel(debug.context_scope || "open")}`,
      variant: "scope",
    },
    {
      label: `关联 session_digest ${debug.related_session_digest_count ?? 0}`,
      variant: "soft",
    },
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
    ? `${project.name} / ${getAccessModeLabel(project.access_mode)}`
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
      ? "当前还没有 working_memory（运行时衔接记忆）。它用于延续当前会话，不等于消息历史。"
      : "当前没有选中会话。请先在左侧导航中创建或选择会话。",
  );

  renderMemoryField(
    elements.sessionDigestText,
    elements.sessionDigestBadge,
    memory?.session_digest || null,
    hasSession
      ? "当前还没有 session_digest（跨会话摘要）。它用于跨会话引用，不等于消息历史。"
      : "当前没有选中会话。请先在左侧导航中创建或选择会话。",
  );
}

function isEditingLatestTurn(state) {
  return Boolean(
    state.ui.latestTurnEdit?.active &&
      state.ui.latestTurnEdit.sessionId &&
      state.ui.latestTurnEdit.sessionId === state.currentSessionId,
  );
}

function renderComposerState(state, elements) {
  const session = state.selectedSessionDetail;
  const missingSelection = !session;
  const locked = session?.status === "archived";
  const disabled = state.busy.chat || missingSelection || locked;

  elements.sendButton.disabled = disabled;
  elements.sendButton.textContent = "发送";
  elements.messageInput.disabled = disabled;

  if (elements.cancelLatestTurnEditButton) {
    elements.cancelLatestTurnEditButton.textContent = "取消编辑";
    elements.cancelLatestTurnEditButton.className = "ghost-button hidden";
    elements.cancelLatestTurnEditButton.disabled = true;
  }

  if (state.busy.chat) {
    elements.composerHint.textContent = "正在发送消息，请稍候...";
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

  elements.composerHint.textContent = isEditingLatestTurn(state)
    ? "你正在消息卡片内编辑最新一轮。主输入框仍用于发送新消息。"
    : "Shift + Enter 换行，Enter 发送。";
  elements.messageInput.placeholder =
    "继续当前会话，观察 working_memory、session_digest、sources 和 debug 字段变化。";
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

function buildMessageActionButton({
  label,
  action,
  messageIndex,
  disabled = false,
  title = "",
}) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "message-action-button ghost-button";
  button.dataset.messageAction = action;
  button.dataset.messageIndex = String(messageIndex);
  button.textContent = label;
  button.title = title || label;
  button.setAttribute("aria-label", title || label);
  button.disabled = disabled;
  return button;
}

function getInlineEditState(state, messages, latestTurnState) {
  const editState = state.ui.latestTurnEdit || {};
  const isCurrentSessionEdit =
    Boolean(editState.active) && editState.sessionId === state.currentSessionId;
  const messageIndex = isCurrentSessionEdit ? Number(editState.messageIndex) : -1;
  const isLatestUserEdit = messageIndex >= 0 && messageIndex === latestTurnState.latestUserIndex;

  return {
    active: isLatestUserEdit,
    messageIndex: isLatestUserEdit ? messageIndex : -1,
    originalContent: isLatestUserEdit ? editState.originalContent || "" : "",
    draft: isLatestUserEdit ? editState.draft || "" : "",
    isDirty: isLatestUserEdit ? (editState.draft || "") !== (editState.originalContent || "") : false,
    canSubmit:
      isLatestUserEdit &&
      !state.busy.chat &&
      !latestTurnState.isArchived &&
      Boolean((editState.draft || "").trim()) &&
      (editState.draft || "") !== (editState.originalContent || ""),
    message: isLatestUserEdit ? messages[messageIndex] || null : null,
  };
}

function buildInlineEditNode(index, inlineEditState, isBusy) {
  const wrapper = document.createElement("div");
  wrapper.className = "message-inline-editor";

  const textarea = document.createElement("textarea");
  textarea.className = "text-area message-inline-editor-input";
  textarea.rows = 3;
  textarea.value = inlineEditState.draft;
  textarea.disabled = isBusy;
  textarea.dataset.latestTurnEditInput = String(index);
  textarea.setAttribute("aria-label", "编辑最新用户消息");
  wrapper.appendChild(textarea);

  const hint = document.createElement("p");
  hint.className = "hint-text message-inline-editor-hint";
  hint.textContent = "修改后会替换最新一轮并重新生成回复。";
  wrapper.appendChild(hint);

  const actions = document.createElement("div");
  actions.className = "message-inline-editor-actions";
  actions.append(
    buildMessageActionButton({
      label: "取消",
      action: "cancel-edit-latest-turn",
      messageIndex: index,
      disabled: isBusy,
      title: "取消本次编辑",
    }),
    buildMessageActionButton({
      label: "发送",
      action: "submit-edit-latest-turn",
      messageIndex: index,
      disabled: !inlineEditState.canSubmit,
      title: inlineEditState.canSubmit ? "发送编辑后的最新用户消息" : "请先修改内容后再发送",
    }),
  );
  wrapper.appendChild(actions);

  return wrapper;
}

function buildMessageActions(index, message, latestTurnState, inlineEditState) {
  const isLatestUser = latestTurnState.latestUserIndex === index;
  const isLatestAssistant = latestTurnState.latestAssistantIndex === index;

  if (inlineEditState.active && inlineEditState.messageIndex === index) {
    return null;
  }

  const container = document.createElement("div");
  container.className = "message-actions";
  container.appendChild(
    buildMessageActionButton({
      label: "复制",
      action: "copy-message",
      messageIndex: index,
      title: message.role === "assistant" ? "复制助手消息" : "复制用户消息",
    }),
  );

  if (isLatestUser) {
    container.appendChild(
      buildMessageActionButton({
        label: "编辑消息",
        action: "edit-latest-turn",
        messageIndex: index,
        disabled: latestTurnState.isArchived,
        title: latestTurnState.isArchived
          ? "当前会话已归档，不能编辑最新一轮。"
          : "编辑最新用户消息",
      }),
    );
  }

  if (isLatestAssistant) {
    container.appendChild(
      buildMessageActionButton({
        label: "重答",
        action: "regenerate-latest-turn",
        messageIndex: index,
        disabled: latestTurnState.isArchived,
        title: latestTurnState.isArchived
          ? "当前会话已归档，不能重答最新一轮。"
          : "重新生成最新助手回复",
      }),
    );
  }

  return container;
}

function buildMessageNode(message, index, latestTurnState, inlineEditState, template, state) {
  const node = template.content.firstElementChild.cloneNode(true);
  node.classList.add(`message-${message.role}`);

  const isLatestUser = latestTurnState.latestUserIndex === index;
  const isLatestAssistant = latestTurnState.latestAssistantIndex === index;
  const isInlineEditing = inlineEditState.active && inlineEditState.messageIndex === index;
  node.classList.toggle("message-card-latest-turn", isLatestUser || isLatestAssistant);
  node.classList.toggle("message-card-latest-user", isLatestUser);
  node.classList.toggle("message-card-latest-assistant", isLatestAssistant);
  node.classList.toggle("message-card-editing", isInlineEditing);

  node.querySelector(".message-role").textContent = getRoleLabel(message.role);
  node.querySelector(".message-time").textContent = formatTime(message.timestamp);

  const actions = buildMessageActions(index, message, latestTurnState, inlineEditState);
  const actionsContainer = node.querySelector(".message-actions");
  if (!actions) {
    actionsContainer.remove();
  } else {
    actionsContainer.replaceWith(actions);
  }

  const contentNode = node.querySelector(".message-content");
  if (isInlineEditing) {
    contentNode.replaceWith(buildInlineEditNode(index, inlineEditState, state.busy.chat));
  } else {
    contentNode.textContent = message.content;
  }

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
    String(
      message?.debug?.related_session_digest_count ?? message?.debug?.related_summary_count ?? "",
    ),
  ].join("|");
}

function getLatestTurnRenderState(state, messages) {
  const latestTurn = getLatestTurnIndexes(messages);
  const editState = state.ui.latestTurnEdit || {};
  const isCurrentSessionEdit =
    Boolean(editState.active) && editState.sessionId === state.currentSessionId;
  const editingMessageIndex = isCurrentSessionEdit ? Number(editState.messageIndex) : -1;
  const editDraft = isCurrentSessionEdit ? editState.draft || "" : "";
  const editOriginalContent = isCurrentSessionEdit ? editState.originalContent || "" : "";

  return {
    ...latestTurn,
    isArchived: state.selectedSessionDetail?.status === "archived",
    editingMessageIndex,
    editStateKey: isCurrentSessionEdit
      ? `${editingMessageIndex}|${editOriginalContent}|${editDraft}`
      : "idle",
    sessionStatusKey: state.selectedSessionDetail?.status || "none",
  };
}

function updateMessageRenderCache(sessionId, messages, latestTurnState) {
  messageRenderCache.sessionId = sessionId;
  messageRenderCache.messagesRef = messages;
  messageRenderCache.messageCount = messages.length;
  messageRenderCache.lastMessageKey = messages.length
    ? getMessageKey(messages[messages.length - 1])
    : "";
  messageRenderCache.emptyStateKey = sessionId ? "empty-session" : "empty-selection";
  messageRenderCache.latestUserIndex = latestTurnState.latestUserIndex;
  messageRenderCache.latestAssistantIndex = latestTurnState.latestAssistantIndex;
  messageRenderCache.sessionStatusKey = latestTurnState.sessionStatusKey;
  messageRenderCache.editStateKey = latestTurnState.editStateKey;
  messageRenderCache.editingMessageIndex = latestTurnState.editingMessageIndex;
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
  updateMessageRenderCache(sessionId, [], getLatestTurnRenderState(state, []));
}

function rerenderAffectedNodes(elements, messages, latestTurnState, inlineEditState, template, state, indexes) {
  const uniqueIndexes = [...new Set(indexes.filter((value) => value >= 0 && value < messages.length))];
  uniqueIndexes.forEach((index) => {
    const nextNode = buildMessageNode(
      messages[index],
      index,
      latestTurnState,
      inlineEditState,
      template,
      state,
    );
    const currentNode = elements.messageList.children[index];
    if (currentNode) {
      currentNode.replaceWith(nextNode);
    }
  });
}

function renderMessages(state, elements) {
  const sessionId = state.currentSessionId || null;
  const messages = sessionId ? getMessagesForCurrentSession() : [];
  const latestTurnState = getLatestTurnRenderState(state, messages);
  const inlineEditState = getInlineEditState(state, messages, latestTurnState);

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
  const sameActionState =
    messageRenderCache.latestUserIndex === latestTurnState.latestUserIndex &&
    messageRenderCache.latestAssistantIndex === latestTurnState.latestAssistantIndex &&
    messageRenderCache.sessionStatusKey === latestTurnState.sessionStatusKey &&
    messageRenderCache.editStateKey === latestTurnState.editStateKey;

  if (sameSession && sameArrayRef && sameTail && sameActionState) {
    return;
  }

  elements.chatEmptyState.hidden = true;
  elements.chatEmptyState.innerHTML = "";

  const canPatchExistingNodes =
    sameSession &&
    sameArrayRef &&
    sameTail &&
    elements.messageList.childElementCount === messages.length;

  if (canPatchExistingNodes) {
    rerenderAffectedNodes(
      elements,
      messages,
      latestTurnState,
      inlineEditState,
      elements.messageTemplate,
      state,
      [
        messageRenderCache.latestUserIndex,
        messageRenderCache.latestAssistantIndex,
        latestTurnState.latestUserIndex,
        latestTurnState.latestAssistantIndex,
        messageRenderCache.editingMessageIndex,
        latestTurnState.editingMessageIndex,
      ],
    );
    updateMessageRenderCache(sessionId, messages, latestTurnState);
    return;
  }

  const canAppendOnly =
    sameSession &&
    sameArrayRef &&
    messageRenderCache.sessionStatusKey === latestTurnState.sessionStatusKey &&
    messageRenderCache.editStateKey === latestTurnState.editStateKey &&
    messages.length > messageRenderCache.messageCount &&
    elements.messageList.childElementCount === messageRenderCache.messageCount;

  if (canAppendOnly) {
    const previousIndexes = [
      messageRenderCache.latestUserIndex,
      messageRenderCache.latestAssistantIndex,
      messageRenderCache.editingMessageIndex,
    ];

    for (let index = messageRenderCache.messageCount; index < messages.length; index += 1) {
      elements.messageList.appendChild(
        buildMessageNode(
          messages[index],
          index,
          latestTurnState,
          inlineEditState,
          elements.messageTemplate,
          state,
        ),
      );
    }

    rerenderAffectedNodes(
      elements,
      messages,
      latestTurnState,
      inlineEditState,
      elements.messageTemplate,
      state,
      [
        ...previousIndexes,
        latestTurnState.latestUserIndex,
        latestTurnState.latestAssistantIndex,
        latestTurnState.editingMessageIndex,
      ],
    );

    updateMessageRenderCache(sessionId, messages, latestTurnState);
    elements.messageList.scrollTop = elements.messageList.scrollHeight;
    return;
  }

  elements.messageList.innerHTML = "";
  messages.forEach((message, index) => {
    elements.messageList.appendChild(
      buildMessageNode(
        message,
        index,
        latestTurnState,
        inlineEditState,
        elements.messageTemplate,
        state,
      ),
    );
  });
  updateMessageRenderCache(sessionId, messages, latestTurnState);
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
