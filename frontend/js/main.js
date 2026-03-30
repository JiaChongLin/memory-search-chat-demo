import { getAccessModeLabel } from "./labels.js";
import {
  archiveSession,
  createProject,
  createSession,
  deleteSession,
  getSession,
  healthCheck,
  listProjects,
  listSessions,
  moveSession,
  normalizeBaseUrl,
  sendChat,
} from "./api.js";
import { renderChat } from "./render-chat.js";
import { renderManagement } from "./render-management.js";
import {
  appendMessage,
  clearNotice,
  getState,
  setBackendBaseUrl,
  setBusy,
  setChatDebug,
  setCurrentProjectId,
  setCurrentSessionId,
  setHealth,
  setNewChatMenuOpen,
  setNotice,
  setProjectModalOpen,
  setProjects,
  setSelectedProjectDetail,
  setSelectedSessionDetail,
  setSessions,
  setSummaryForSession,
  subscribe,
  toggleProjectExpanded,
  toggleProjectSessionExpansion,
  toggleShowAllProjects,
  toggleSidebarSection,
} from "./state.js";

const elements = {
  backendBaseUrl: document.querySelector("#backendBaseUrl"),
  saveConfigButton: document.querySelector("#saveConfigButton"),
  checkHealthButton: document.querySelector("#checkHealthButton"),
  newChatButton: document.querySelector("#newChatButton"),
  searchChatsButton: document.querySelector("#searchChatsButton"),
  projectForm: document.querySelector("#projectForm"),
  composerForm: document.querySelector("#composerForm"),
  projectsSection: document.querySelector("#projectsSection"),
  unassignedSection: document.querySelector("#unassignedSection"),
  sessionDetail: document.querySelector("#sessionDetail"),
  projectNotice: document.querySelector("#projectNotice"),
  sessionNotice: document.querySelector("#sessionNotice"),
  sessionBanner: document.querySelector("#sessionBanner"),
  chatNotice: document.querySelector("#chatNotice"),
  globalNotice: document.querySelector("#globalNotice"),
  currentProjectLabel: document.querySelector("#currentProjectLabel"),
  currentSessionLabel: document.querySelector("#currentSessionLabel"),
  healthBadge: document.querySelector("#healthBadge"),
  environmentValue: document.querySelector("#environmentValue"),
  projectModal: document.querySelector("#projectModal"),
  projectNameInput: document.querySelector("#projectNameInput"),
  projectDescriptionInput: document.querySelector("#projectDescriptionInput"),
  projectAccessSelect: document.querySelector("#projectAccessSelect"),
  messageInput: document.querySelector("#messageInput"),
  sendButton: document.querySelector("#sendButton"),
  composerHint: document.querySelector("#composerHint"),
  summaryBadge: document.querySelector("#summaryBadge"),
  summaryText: document.querySelector("#summaryText"),
  debugInfo: document.querySelector("#debugInfo"),
  debugNote: document.querySelector("#debugNote"),
  selectionHint: document.querySelector("#selectionHint"),
  messageList: document.querySelector("#messageList"),
  chatEmptyState: document.querySelector("#chatEmptyState"),
  messageTemplate: document.querySelector("#messageTemplate"),
  newChatMenu: document.querySelector("#newChatMenu"),
  quickChips: document.querySelectorAll(".quick-chip"),
};

function formatErrorMessage(error) {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "未知错误";
}

function parseOptionalProjectId(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  if (value === "__none__") {
    return null;
  }
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? null : parsed;
}

function getBaseUrl() {
  return normalizeBaseUrl(elements.backendBaseUrl.value || getState().backendBaseUrl);
}

function buildAssistantDebug(responseData) {
  return {
    session_id: responseData.session_id,
    context_scope: responseData.context_scope,
    related_summary_count: responseData.related_summary_count,
    used_live_model: responseData.used_live_model,
    fallback_reason: responseData.fallback_reason,
    search_triggered: responseData.search_triggered,
    search_used: responseData.search_used,
  };
}

function canChatWithCurrentSelection() {
  const state = getState();
  const session = state.selectedSessionDetail;
  if (!session) {
    return false;
  }
  return !["archived", "deleted"].includes(session.status);
}

function syncProjectSelection(projectId) {
  const state = getState();
  if (projectId === null || projectId === undefined) {
    setCurrentProjectId(null);
    setSelectedProjectDetail(null);
    return;
  }

  const project = state.projects.find((item) => item.id === projectId) || null;
  setCurrentProjectId(projectId);
  setSelectedProjectDetail(project);
}

async function refreshHealth(silent = false) {
  setBusy("health", true);
  try {
    const baseUrl = getBaseUrl();
    const payload = await healthCheck(baseUrl);
    setBackendBaseUrl(baseUrl);
    setHealth({
      status: "success",
      label: "在线",
      environment: payload.environment || "unknown",
    });
    if (!silent) {
      setNotice("global", "后端连接正常。", "success");
    }
  } catch (error) {
    setHealth({
      status: "warning",
      label: "连接失败",
      environment: "不可用",
    });
    if (!silent) {
      setNotice("global", `无法连接后端：${formatErrorMessage(error)}`, "danger");
    }
  } finally {
    setBusy("health", false);
  }
}

async function refreshProjects(options = {}) {
  setBusy("projects", true);
  try {
    const projects = await listProjects(getBaseUrl());
    setProjects(projects);

    const state = getState();
    if (state.currentProjectId !== null) {
      const selected = projects.find((item) => item.id === state.currentProjectId) || null;
      setSelectedProjectDetail(selected);
      if (!selected) {
        setCurrentProjectId(null);
      }
    }

    if (!options.silent) {
      clearNotice("projects");
    }
  } catch (error) {
    setNotice("projects", `加载项目失败：${formatErrorMessage(error)}`, "danger");
  } finally {
    setBusy("projects", false);
  }
}

async function syncSelectedSessionDetail() {
  const state = getState();
  if (!state.currentSessionId) {
    return;
  }

  const matched = state.sessions.find((item) => item.id === state.currentSessionId);
  if (matched) {
    setSelectedSessionDetail(matched);
    return;
  }

  try {
    const detail = await getSession(getBaseUrl(), state.currentSessionId);
    setSelectedSessionDetail(detail);
  } catch (error) {
    if (error.status === 404) {
      setSelectedSessionDetail(null);
      return;
    }
    setNotice("sessions", `读取会话详情失败：${formatErrorMessage(error)}`, "warning");
  }
}

async function refreshSessions(options = {}) {
  setBusy("sessions", true);
  try {
    const sessions = await listSessions(getBaseUrl());
    setSessions(sessions);
    await syncSelectedSessionDetail();

    if (!options.silent) {
      clearNotice("sessions");
    }
  } catch (error) {
    setNotice("sessions", `加载会话失败：${formatErrorMessage(error)}`, "danger");
  } finally {
    setBusy("sessions", false);
  }
}

async function handleProjectCreate(event) {
  event.preventDefault();

  const payload = {
    name: elements.projectNameInput.value.trim(),
    description: elements.projectDescriptionInput.value.trim() || null,
    access_mode: elements.projectAccessSelect.value,
  };

  if (!payload.name) {
    setNotice("projects", "项目名称不能为空。", "warning");
    return;
  }

  try {
    setBusy("projects", true);
    const project = await createProject(getBaseUrl(), payload);
    setProjectModalOpen(false);
    setCurrentProjectId(project.id);
    setSelectedProjectDetail(project);
    elements.projectForm.reset();
    elements.projectAccessSelect.value = "open";
    setNotice(
      "projects",
      `项目 ${project.name} 创建成功，访问模式：${getAccessModeLabel(project.access_mode)}。`,
      "success",
    );
    await refreshProjects({ silent: true });
    await refreshSessions({ silent: true });
  } catch (error) {
    setNotice("projects", `创建项目失败：${formatErrorMessage(error)}`, "danger");
  } finally {
    setBusy("projects", false);
  }
}

function handleProjectSelect(projectId) {
  const state = getState();
  if (state.currentProjectId === projectId) {
    setCurrentProjectId(null);
    setSelectedProjectDetail(null);
    setNewChatMenuOpen(false);
    return;
  }

  syncProjectSelection(projectId);
  clearNotice("projects");
}

async function createBlankSession(projectId = null) {
  try {
    setBusy("sessions", true);
    const session = await createSession(getBaseUrl(), {
      title: null,
      project_id: projectId,
      is_private: false,
    });
    setCurrentSessionId(session.id);
    setSelectedSessionDetail(session);
    setSummaryForSession(session.id, null);
    syncProjectSelection(session.project_id);
    setNewChatMenuOpen(false);
    setNotice(
      "sessions",
      projectId === null ? "已创建未归属会话。" : "已在当前项目下创建新聊天。",
      "success",
    );
    await refreshSessions({ silent: true });
  } catch (error) {
    setNotice("sessions", `创建会话失败：${formatErrorMessage(error)}`, "danger");
  } finally {
    setBusy("sessions", false);
  }
}

function handleNewChatClick() {
  const state = getState();
  if (state.selectedProjectDetail) {
    setNewChatMenuOpen(!state.ui.newChatMenuOpen);
    return;
  }
  createBlankSession(null);
}

function handleSessionSelect(sessionId) {
  const state = getState();
  const session = state.sessions.find((item) => item.id === sessionId) || null;
  setCurrentSessionId(sessionId);
  setSelectedSessionDetail(session);
  clearNotice("chat");
  setNewChatMenuOpen(false);
  if (session) {
    syncProjectSelection(session.project_id);
  }
}

async function handleArchiveSession(sessionId) {
  try {
    const session = await archiveSession(getBaseUrl(), sessionId);
    setSelectedSessionDetail(session);
    setNotice("sessions", `会话 ${sessionId.slice(0, 10)} 已归档。`, "success");
    await refreshSessions({ silent: true });
  } catch (error) {
    setNotice("sessions", `归档失败：${formatErrorMessage(error)}`, "danger");
  }
}

async function handleDeleteSession(sessionId) {
  try {
    const session = await deleteSession(getBaseUrl(), sessionId);
    setSelectedSessionDetail(session);
    setNotice("sessions", `会话 ${sessionId.slice(0, 10)} 已软删除。`, "warning");
    await refreshSessions({ silent: true });
  } catch (error) {
    setNotice("sessions", `删除失败：${formatErrorMessage(error)}`, "danger");
  }
}

async function handleMoveSession() {
  const state = getState();
  if (!state.currentSessionId) {
    setNotice("sessions", "请先选择一个会话。", "warning");
    return;
  }

  const moveSelect = document.querySelector("#moveProjectSelect");
  const rawValue = moveSelect?.value || "";
  if (!rawValue) {
    setNotice("sessions", "请选择目标项目或移出项目。", "warning");
    return;
  }

  const targetProjectId = parseOptionalProjectId(rawValue);

  try {
    const session = await moveSession(getBaseUrl(), state.currentSessionId, targetProjectId);
    setSelectedSessionDetail(session);
    syncProjectSelection(session.project_id);
    setNotice(
      "sessions",
      targetProjectId === null
        ? "会话已移出项目，现在是未归属会话。"
        : "会话已移动到目标项目。",
      "success",
    );
    await refreshSessions({ silent: true });
  } catch (error) {
    setNotice("sessions", `移动失败：${formatErrorMessage(error)}`, "danger");
  }
}

async function handleChatSubmit(event) {
  event.preventDefault();

  const message = elements.messageInput.value.trim();
  if (!message) {
    return;
  }

  const stateBeforeSend = getState();
  if (!stateBeforeSend.currentSessionId) {
    setNotice("chat", "当前没有选中会话。请先在左侧选择或创建会话。", "warning");
    return;
  }

  if (!canChatWithCurrentSelection()) {
    setNotice("chat", "当前会话已归档或删除，请切换到可写会话。", "warning");
    return;
  }

  appendMessage(stateBeforeSend.currentSessionId, {
    role: "user",
    content: message,
    timestamp: Date.now(),
    sources: [],
  });
  elements.messageInput.value = "";
  clearNotice("chat");
  setBusy("chat", true);

  try {
    const response = await sendChat(getBaseUrl(), {
      message,
      session_id: stateBeforeSend.currentSessionId,
    });

    setCurrentSessionId(response.session_id);
    setSelectedSessionDetail({
      id: response.session_id,
      title: stateBeforeSend.selectedSessionDetail?.title || null,
      project_id: stateBeforeSend.selectedSessionDetail?.project_id || null,
      status: "active",
      is_private: stateBeforeSend.selectedSessionDetail?.is_private || false,
      updated_at: new Date().toISOString(),
    });
    setSummaryForSession(response.session_id, response.summary || null);
    setChatDebug(response.session_id, buildAssistantDebug(response));

    appendMessage(response.session_id, {
      role: "assistant",
      content: response.reply,
      timestamp: Date.now(),
      sources: response.sources || [],
      debug: buildAssistantDebug(response),
    });

    setNotice(
      "chat",
      `已收到回复。后端返回的 context_scope 会继续保留字段名，但现在按“项目访问模式解析结果”理解：${getAccessModeLabel(response.context_scope)}。`,
      "success",
    );
    await refreshSessions({ silent: true });
  } catch (error) {
    appendMessage(stateBeforeSend.currentSessionId, {
      role: "system",
      content: `请求失败：${formatErrorMessage(error)}`,
      timestamp: Date.now(),
      sources: [],
    });
    setNotice("chat", `聊天请求失败：${formatErrorMessage(error)}`, "danger");
  } finally {
    setBusy("chat", false);
  }
}

function handleQuickChipClick(event) {
  const chip = event.target.closest(".quick-chip");
  if (!chip) {
    return;
  }

  elements.messageInput.value = chip.dataset.prompt || "";
  elements.messageInput.focus();
}

function handleComposerKeydown(event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.composerForm.requestSubmit();
  }
}

function handleGlobalClick(event) {
  const sectionToggle = event.target.closest("[data-section-toggle]");
  if (sectionToggle) {
    toggleSidebarSection(sectionToggle.dataset.sectionToggle);
    return;
  }

  const projectMoreToggle = event.target.closest("[data-projects-more-toggle]");
  if (projectMoreToggle) {
    toggleShowAllProjects();
    return;
  }

  const projectToggle = event.target.closest("[data-project-toggle]");
  if (projectToggle) {
    const projectId = Number.parseInt(projectToggle.dataset.projectToggle, 10);
    if (!Number.isNaN(projectId)) {
      toggleProjectExpanded(projectId);
    }
    return;
  }

  const projectSessionToggle = event.target.closest("[data-project-sessions-toggle]");
  if (projectSessionToggle) {
    const projectId = Number.parseInt(projectSessionToggle.dataset.projectSessionsToggle, 10);
    if (!Number.isNaN(projectId)) {
      toggleProjectSessionExpansion(projectId);
    }
    return;
  }

  const projectSelect = event.target.closest("[data-project-select]");
  if (projectSelect) {
    const projectId = Number.parseInt(projectSelect.dataset.projectSelect, 10);
    if (!Number.isNaN(projectId)) {
      handleProjectSelect(projectId);
    }
    return;
  }

  const sessionSelect = event.target.closest("[data-session-select]");
  if (sessionSelect) {
    handleSessionSelect(sessionSelect.dataset.sessionSelect);
    return;
  }

  const archiveButton = event.target.closest("#archiveSessionButton");
  if (archiveButton) {
    const state = getState();
    if (state.currentSessionId) {
      handleArchiveSession(state.currentSessionId);
    }
    return;
  }

  const deleteButton = event.target.closest("#deleteSessionButton");
  if (deleteButton) {
    const state = getState();
    if (state.currentSessionId) {
      handleDeleteSession(state.currentSessionId);
    }
    return;
  }

  const moveButton = event.target.closest("#moveSessionButton");
  if (moveButton) {
    handleMoveSession();
    return;
  }

  if (event.target.closest("#openProjectModalButton")) {
    setProjectModalOpen(true);
    setNewChatMenuOpen(false);
    return;
  }

  if (
    event.target.closest("#closeProjectModalButton") ||
    event.target.closest("[data-close-project-modal]")
  ) {
    setProjectModalOpen(false);
    return;
  }

  if (event.target.closest("#createChatInProjectButton")) {
    const projectId = getState().currentProjectId;
    createBlankSession(projectId);
    return;
  }

  if (event.target.closest("#createUnassignedChatButton")) {
    createBlankSession(null);
    return;
  }

  if (
    !event.target.closest("#newChatButton") &&
    !event.target.closest("#newChatMenu")
  ) {
    setNewChatMenuOpen(false);
  }
}

function wireEvents() {
  elements.saveConfigButton.addEventListener("click", () => {
    setBackendBaseUrl(normalizeBaseUrl(elements.backendBaseUrl.value));
    refreshHealth();
  });
  elements.checkHealthButton.addEventListener("click", () => refreshHealth());
  elements.newChatButton.addEventListener("click", handleNewChatClick);
  elements.searchChatsButton.addEventListener("click", () => {
    setNotice("global", "搜索聊天入口已预留，后续再接真实搜索能力。", "info");
  });
  elements.projectForm.addEventListener("submit", handleProjectCreate);
  elements.composerForm.addEventListener("submit", handleChatSubmit);
  elements.messageInput.addEventListener("keydown", handleComposerKeydown);
  elements.quickChips.forEach((chip) => chip.addEventListener("click", handleQuickChipClick));
  document.addEventListener("click", handleGlobalClick);
}

function renderAll(state) {
  renderManagement(state, elements);
  renderChat(state, elements);
}

async function bootstrap() {
  subscribe(renderAll);
  wireEvents();
  await refreshHealth(true);
  await refreshProjects({ silent: true });
  await refreshSessions({ silent: true });
}

bootstrap();
