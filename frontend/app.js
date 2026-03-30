const STORAGE_KEYS = {
  backendBaseUrl: "memory-search-chat-demo.backendBaseUrl",
  sessionId: "memory-search-chat-demo.sessionId",
  summary: "memory-search-chat-demo.summary",
  messages: "memory-search-chat-demo.messages",
};

const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8000";

const state = {
  backendBaseUrl:
    localStorage.getItem(STORAGE_KEYS.backendBaseUrl) || DEFAULT_BACKEND_BASE_URL,
  sessionId: localStorage.getItem(STORAGE_KEYS.sessionId),
  summary: localStorage.getItem(STORAGE_KEYS.summary),
  messages: loadMessages(),
  sending: false,
};

const elements = {
  backendBaseUrl: document.querySelector("#backendBaseUrl"),
  saveConfigButton: document.querySelector("#saveConfigButton"),
  checkHealthButton: document.querySelector("#checkHealthButton"),
  resetSessionButton: document.querySelector("#resetSessionButton"),
  healthBadge: document.querySelector("#healthBadge"),
  sessionIdValue: document.querySelector("#sessionIdValue"),
  environmentValue: document.querySelector("#environmentValue"),
  summaryBadge: document.querySelector("#summaryBadge"),
  summaryText: document.querySelector("#summaryText"),
  runtimeHint: document.querySelector("#runtimeHint"),
  messageList: document.querySelector("#messageList"),
  welcomeMessage: document.querySelector("#welcomeMessage"),
  messageTemplate: document.querySelector("#messageTemplate"),
  composerForm: document.querySelector("#composerForm"),
  composerHint: document.querySelector("#composerHint"),
  messageInput: document.querySelector("#messageInput"),
  sendButton: document.querySelector("#sendButton"),
  quickChips: document.querySelectorAll(".quick-chip"),
};

bootstrap();

function bootstrap() {
  elements.backendBaseUrl.value = state.backendBaseUrl;
  wireEvents();
  renderSidebar();
  renderMessages();
  checkBackendHealth();
}

function wireEvents() {
  elements.saveConfigButton.addEventListener("click", handleSaveConfig);
  elements.checkHealthButton.addEventListener("click", checkBackendHealth);
  elements.resetSessionButton.addEventListener("click", resetSession);
  elements.composerForm.addEventListener("submit", handleComposerSubmit);
  elements.messageInput.addEventListener("keydown", handleComposerKeydown);

  elements.quickChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      elements.messageInput.value = chip.dataset.prompt || "";
      elements.messageInput.focus();
    });
  });
}

function loadMessages() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.messages);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persistState() {
  localStorage.setItem(STORAGE_KEYS.backendBaseUrl, state.backendBaseUrl);

  if (state.sessionId) {
    localStorage.setItem(STORAGE_KEYS.sessionId, state.sessionId);
  } else {
    localStorage.removeItem(STORAGE_KEYS.sessionId);
  }

  if (state.summary) {
    localStorage.setItem(STORAGE_KEYS.summary, state.summary);
  } else {
    localStorage.removeItem(STORAGE_KEYS.summary);
  }

  localStorage.setItem(STORAGE_KEYS.messages, JSON.stringify(state.messages));
}

function renderSidebar() {
  elements.sessionIdValue.textContent = state.sessionId || "未创建";

  if (state.summary) {
    elements.summaryText.textContent = state.summary;
    elements.summaryBadge.textContent = "摘要已生成";
    elements.summaryBadge.className = "pill pill-success";
  } else {
    elements.summaryText.textContent =
      "当前会话还没有生成摘要。多聊几轮后，这里会显示后端返回的压缩记忆。";
    elements.summaryBadge.textContent = "无摘要";
    elements.summaryBadge.className = "pill pill-soft";
  }
}

function renderMessages() {
  const dynamicMessages = elements.messageList.querySelectorAll("[data-rendered='true']");
  dynamicMessages.forEach((node) => node.remove());

  elements.welcomeMessage.hidden = state.messages.length > 0;

  state.messages.forEach((message) => {
    elements.messageList.appendChild(buildMessageNode(message));
  });

  elements.messageList.scrollTop = elements.messageList.scrollHeight;
}

function buildMessageNode(message) {
  const node = elements.messageTemplate.content.firstElementChild.cloneNode(true);
  node.dataset.rendered = "true";
  node.classList.add(message.role);

  const roleLabel = node.querySelector(".message-role");
  const content = node.querySelector(".message-content");
  const meta = node.querySelector(".message-meta");
  const sourceList = node.querySelector(".source-list");

  roleLabel.textContent = message.role === "user" ? "用户" : "助手";
  content.textContent = message.content;

  if (Array.isArray(message.meta) && message.meta.length > 0) {
    message.meta.forEach((item) => {
      const chip = document.createElement("span");
      chip.className = `meta-chip ${item.variant}`;
      chip.textContent = item.label;
      meta.appendChild(chip);
    });
  } else {
    meta.remove();
  }

  if (Array.isArray(message.sources) && message.sources.length > 0) {
    message.sources.forEach((source) => {
      const card = document.createElement("a");
      card.className = "source-card";
      card.href = source.url;
      card.target = "_blank";
      card.rel = "noreferrer";

      const title = document.createElement("strong");
      title.textContent = source.title;

      const snippet = document.createElement("span");
      snippet.textContent = source.snippet || source.url;

      card.append(title, snippet);
      sourceList.appendChild(card);
    });
  } else {
    sourceList.remove();
  }

  return node;
}

function setHealthBadge(variant, text) {
  elements.healthBadge.className = `pill ${variant}`;
  elements.healthBadge.textContent = text;
}

async function checkBackendHealth() {
  const baseUrl = normalizeBaseUrl(elements.backendBaseUrl.value);
  elements.environmentValue.textContent = "检测中";
  setHealthBadge("pill-soft", "检测中");

  try {
    const response = await fetch(`${baseUrl}/health`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    state.backendBaseUrl = baseUrl;
    persistState();

    elements.backendBaseUrl.value = state.backendBaseUrl;
    elements.environmentValue.textContent = data.environment || "unknown";
    setHealthBadge("pill-success", "后端在线");
    elements.runtimeHint.textContent = "后端连接正常，可以直接开始发送消息。";
  } catch (error) {
    elements.environmentValue.textContent = "不可用";
    setHealthBadge("pill-warning", "连接失败");
    elements.runtimeHint.textContent =
      `无法连接到后端：${formatErrorMessage(error)}。请确认 FastAPI 已启动。`;
  }
}

function handleSaveConfig() {
  state.backendBaseUrl = normalizeBaseUrl(elements.backendBaseUrl.value);
  elements.backendBaseUrl.value = state.backendBaseUrl;
  persistState();
  checkBackendHealth();
}

function handleComposerKeydown(event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.composerForm.requestSubmit();
  }
}

async function handleComposerSubmit(event) {
  event.preventDefault();

  const message = elements.messageInput.value.trim();
  if (!message || state.sending) {
    return;
  }

  appendMessage({ role: "user", content: message, meta: [], sources: [] });
  elements.messageInput.value = "";
  setSending(true, "正在等待后端返回...");

  try {
    const response = await fetch(`${state.backendBaseUrl}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message,
        session_id: state.sessionId,
      }),
    });

    const data = await parseJsonResponse(response);
    if (!response.ok) {
      throw new Error(data?.error?.message || `HTTP ${response.status}`);
    }

    state.sessionId = data.session_id;
    state.summary = data.summary || null;

    appendMessage({
      role: "assistant",
      content: data.reply,
      meta: buildAssistantMeta(data),
      sources: data.sources || [],
    });

    persistState();
    renderSidebar();
    elements.runtimeHint.textContent = buildRuntimeHint(data);
  } catch (error) {
    appendMessage({
      role: "assistant",
      content: `请求失败：${formatErrorMessage(error)}`,
      meta: [{ label: "接口异常", variant: "meta-error" }],
      sources: [],
    });
    elements.runtimeHint.textContent =
      "这次请求没有成功返回。你可以先检查后端日志，或者点左侧“检查后端”。";
  } finally {
    setSending(false, "Shift + Enter 换行，Enter 发送");
  }
}

function appendMessage(message) {
  state.messages.push(message);
  persistState();
  elements.messageList.appendChild(buildMessageNode(message));
  elements.messageList.scrollTop = elements.messageList.scrollHeight;
}

function buildAssistantMeta(data) {
  const meta = [];

  if (data.used_live_model) {
    meta.push({ label: "在线模型", variant: "meta-live" });
  } else {
    meta.push({ label: "本地降级", variant: "meta-fallback" });
  }

  if (data.search_triggered && data.search_used) {
    meta.push({ label: "已使用搜索结果", variant: "meta-search" });
  } else if (data.search_triggered) {
    meta.push({ label: "触发了搜索", variant: "meta-search" });
  }

  if (data.fallback_reason) {
    meta.push({ label: `原因：${truncate(data.fallback_reason, 40)}`, variant: "meta-error" });
  }

  return meta;
}

function buildRuntimeHint(data) {
  if (data.used_live_model) {
    return data.search_used
      ? "这次回复走了在线模型，并且成功带上了搜索结果。"
      : "这次回复走了在线模型。";
  }

  return data.fallback_reason
    ? `这次回复走了降级路径：${data.fallback_reason}`
    : "这次回复走了本地降级路径。";
}

function setSending(sending, hintText) {
  state.sending = sending;
  elements.sendButton.disabled = sending;
  elements.saveConfigButton.disabled = sending;
  elements.checkHealthButton.disabled = sending;
  elements.resetSessionButton.disabled = sending;
  elements.composerHint.textContent = hintText;
}

function resetSession() {
  state.sessionId = null;
  state.summary = null;
  state.messages = [];
  persistState();
  renderSidebar();
  renderMessages();
  elements.runtimeHint.textContent =
    "已清空前端缓存并准备新会话。发送下一条消息时会自动创建新的 session。";
}

function normalizeBaseUrl(value) {
  const normalized = value.trim().replace(/\/+$/, "");
  return normalized || DEFAULT_BACKEND_BASE_URL;
}

async function parseJsonResponse(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function formatErrorMessage(error) {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "未知错误";
}

function truncate(value, maxLength) {
  if (!value || value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 1)}…`;
}
