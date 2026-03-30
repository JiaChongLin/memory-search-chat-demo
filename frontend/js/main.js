import { getAccessModeLabel, getSessionTitle } from "./labels.js";
import {
  archiveSession,
  createProject,
  createSession,
  deleteProject,
  deleteSession,
  getSession,
  getSessionMessages,
  healthCheck,
  listProjects,
  listSessions,
  moveSession,
  normalizeBaseUrl,
  sendChat,
  updateProject,
  updateSession,
} from "./api.js";
import { renderChat } from "./render-chat.js";
import { renderManagement } from "./render-management.js";
import {
  appendMessage,
  clearCurrentSessionSelection,
  clearNotice,
  getMessagesForSession,
  getState,
  removeSessionData,
  setBackendBaseUrl,
  setBusy,
  setChatDebug,
  setCurrentProjectId,
  setCurrentSessionId,
  setHealth,
  setMessagesForSession,
  setNewChatMenuOpen,
  setNotice,
  setProjectModalState,
  setProjects,
  setSelectedProjectDetail,
  setSelectedSessionDetail,
  setSessions,
  setSummaryForSession,
  subscribe,
  setProjectExpanded,
  toggleProjectSessionExpansion,
  toggleShowAllProjects,
  toggleShowAllUnassigned,
  toggleSidebarSection,
} from "./state.js";

const elements = {
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
  currentVisibilityBadge: document.querySelector("#currentVisibilityBadge"),
  currentStatusBadge: document.querySelector("#currentStatusBadge"),
  renameSessionButton: document.querySelector("#renameSessionButton"),
  projectModal: document.querySelector("#projectModal"),
  projectModalTitle: document.querySelector("#projectModalTitle"),
  projectModeHint: document.querySelector("#projectModeHint"),
  projectAccessReadonly: document.querySelector("#projectAccessReadonly"),
  projectSubmitButton: document.querySelector("#projectSubmitButton"),
  projectNameInput: document.querySelector("#projectNameInput"),
  projectDescriptionInput: document.querySelector("#projectDescriptionInput"),
  projectAccessSelect: document.querySelector("#projectAccessSelect"),
  confirmModal: document.querySelector("#confirmModal"),
  confirmModalTitle: document.querySelector("#confirmModalTitle"),
  confirmModalBody: document.querySelector("#confirmModalBody"),
  confirmCancelButton: document.querySelector("#confirmCancelButton"),
  confirmAcceptButton: document.querySelector("#confirmAcceptButton"),
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

const COMPOSER_MIN_HEIGHT = 52;
const COMPOSER_MAX_HEIGHT = 188;
const NOTICE_AUTO_DISMISS_MS = 2600;
const NOTICE_FADE_MS = 320;

const noticeTimers = new Map();
let pendingConfirmResolve = null;

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
  return normalizeBaseUrl(getState().backendBaseUrl);
}

function getNoticeElement(scope) {
  if (scope === "projects") {
    return elements.projectNotice;
  }
  if (scope === "sessions") {
    return elements.sessionNotice;
  }
  if (scope === "chat") {
    return elements.chatNotice;
  }
  if (scope === "global") {
    return elements.globalNotice;
  }
  return null;
}

function clearNoticeTimer(scope) {
  const timer = noticeTimers.get(scope);
  if (timer) {
    window.clearTimeout(timer);
    noticeTimers.delete(scope);
  }
}

function showTransientNotice(scope, message, variant = "info", duration = NOTICE_AUTO_DISMISS_MS) {
  clearNoticeTimer(scope);
  setNotice(scope, message, variant);

  const timer = window.setTimeout(() => {
    const element = getNoticeElement(scope);
    if (element) {
      element.classList.add("notice-fading");
    }

    window.setTimeout(() => {
      clearNotice(scope);
      if (element) {
        element.classList.remove("notice-fading");
      }
    }, NOTICE_FADE_MS);
    noticeTimers.delete(scope);
  }, duration);

  noticeTimers.set(scope, timer);
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

function mapApiMessage(message) {
  return {
    role: message.role,
    content: message.content,
    timestamp: message.created_at,
    sources: [],
  };
}

function canChatWithCurrentSelection() {
  const state = getState();
  const session = state.selectedSessionDetail;
  if (!session) {
    return false;
  }
  return session.status !== "archived";
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

function clearSessionSelection() {
  clearCurrentSessionSelection();
}

function resizeComposer() {
  const textarea = elements.messageInput;
  if (!textarea) {
    return;
  }

  textarea.style.height = `${COMPOSER_MIN_HEIGHT}px`;
  const nextHeight = Math.min(textarea.scrollHeight, COMPOSER_MAX_HEIGHT);
  textarea.style.height = `${Math.max(COMPOSER_MIN_HEIGHT, nextHeight)}px`;
  textarea.style.overflowY = textarea.scrollHeight > COMPOSER_MAX_HEIGHT ? "auto" : "hidden";
}

function resetComposer() {
  const textarea = elements.messageInput;
  if (!textarea) {
    return;
  }

  textarea.value = "";
  textarea.style.height = `${COMPOSER_MIN_HEIGHT}px`;
  textarea.style.overflowY = "hidden";
}

function resetProjectForm() {
  elements.projectForm.reset();
  elements.projectAccessSelect.value = "open";
}

function closeProjectModal() {
  setProjectModalState({ isOpen: false, mode: "create", projectId: null });
  resetProjectForm();
}

function closeConfirmModal(result = false) {
  if (elements.confirmModal) {
    elements.confirmModal.classList.add("hidden");
  }

  const resolver = pendingConfirmResolve;
  pendingConfirmResolve = null;
  if (resolver) {
    resolver(Boolean(result));
  }
}

function openConfirmModal({
  title = "确认操作",
  body = "请确认是否继续。",
  confirmLabel = "确认",
  confirmVariant = "danger",
}) {
  if (!elements.confirmModal) {
    return Promise.resolve(false);
  }

  if (pendingConfirmResolve) {
    closeConfirmModal(false);
  }

  elements.confirmModalTitle.textContent = title;
  elements.confirmModalBody.textContent = body;
  elements.confirmAcceptButton.textContent = confirmLabel;
  elements.confirmAcceptButton.className =
    confirmVariant === "danger" ? "danger-button" : "primary-button";
  elements.confirmModal.classList.remove("hidden");

  return new Promise((resolve) => {
    pendingConfirmResolve = resolve;
  });
}
function openProjectCreateModal() {
  resetProjectForm();
  setProjectModalState({ isOpen: true, mode: "create", projectId: null });
  setNewChatMenuOpen(false);
}

function openProjectEditModal(projectId) {
  const state = getState();
  const project = state.projects.find((item) => item.id === projectId) || null;
  if (!project) {
    setNotice("projects", "目标项目不存在，无法编辑。", "warning");
    return;
  }

  elements.projectNameInput.value = project.name || "";
  elements.projectDescriptionInput.value = project.description || "";
  elements.projectAccessSelect.value = project.access_mode;
  setProjectModalState({ isOpen: true, mode: "edit", projectId: project.id });
  setNewChatMenuOpen(false);
  clearNotice("projects");
}

async function ensureSessionMessages(sessionId, options = {}) {
  if (!sessionId) {
    return;
  }

  const force = Boolean(options.force);
  const existingMessages = getMessagesForSession(sessionId);
  if (!force && existingMessages.length > 0) {
    return;
  }

  try {
    const payload = await getSessionMessages(getBaseUrl(), sessionId);
    setMessagesForSession(
      sessionId,
      payload.map((message) => mapApiMessage(message)),
    );
  } catch (error) {
    if (error.status === 404) {
      removeSessionData(sessionId);
      if (getState().currentSessionId === sessionId) {
        clearSessionSelection();
      }
      setNotice("sessions", "该会话不存在，无法回读历史。", "warning");
      return;
    }
    setNotice("sessions", `加载会话历史失败：${formatErrorMessage(error)}`, "warning");
  }
}

async function refreshHealth(silent = false) {
  setBusy("health", true);
  try {
    const baseUrl = getBaseUrl();
    await healthCheck(baseUrl);
    setBackendBaseUrl(baseUrl);
    setHealth({ status: "success", label: "已连接", environment: "connected" });
    if (!silent) {
      clearNotice("global");
    }
  } catch (error) {
    setHealth({ status: "warning", label: "连接异常", environment: "unavailable" });
    if (!silent) {
      setNotice("global", `检查后端失败：${formatErrorMessage(error)}`, "danger");
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
      removeSessionData(state.currentSessionId);
      clearSessionSelection();
      return;
    }
    setNotice("sessions", `同步会话详情失败：${formatErrorMessage(error)}`, "warning");
  }
}

async function refreshSessions(options = {}) {
  setBusy("sessions", true);
  try {
    const sessions = await listSessions(getBaseUrl());
    setSessions(sessions);
    await syncSelectedSessionDetail();

    const state = getState();
    if (state.currentSessionId && options.loadMessages !== false) {
      await ensureSessionMessages(state.currentSessionId, { force: Boolean(options.forceMessages) });
    }

    if (!options.silent) {
      clearNotice("sessions");
    }
  } catch (error) {
    setNotice("sessions", `加载会话失败：${formatErrorMessage(error)}`, "danger");
  } finally {
    setBusy("sessions", false);
  }
}

async function handleProjectSubmit(event) {
  event.preventDefault();

  const state = getState();
  const payload = {
    name: elements.projectNameInput.value.trim(),
    description: elements.projectDescriptionInput.value.trim() || null,
  };

  if (!payload.name) {
    setNotice("projects", "项目名称不能为空。", "warning");
    return;
  }

  try {
    setBusy("projects", true);

    if (state.ui.projectModalMode === "edit") {
      const projectId = state.ui.editingProjectId;
      if (!projectId) {
        setNotice("projects", "当前没有可编辑的项目。", "warning");
        return;
      }

      const updated = await updateProject(getBaseUrl(), projectId, payload);
      if (state.currentProjectId === updated.id) {
        setSelectedProjectDetail(updated);
      }
      closeProjectModal();
      showTransientNotice("projects", `项目 ${updated.name} 已更新。`, "success");
      await refreshProjects({ silent: true });
      return;
    }

    const project = await createProject(getBaseUrl(), {
      ...payload,
      access_mode: elements.projectAccessSelect.value,
    });
    closeProjectModal();
    setCurrentProjectId(project.id);
    setSelectedProjectDetail(project);
    showTransientNotice(
      "projects",
      `项目 ${project.name} 已创建，访问模式为 ${getAccessModeLabel(project.access_mode)}。`,
      "success",
    );
    await refreshProjects({ silent: true });
    await refreshSessions({ silent: true });
  } catch (error) {
    const actionText = state.ui.projectModalMode === "edit" ? "更新项目" : "创建项目";
    setNotice("projects", `${actionText}失败：${formatErrorMessage(error)}`, "danger");
  } finally {
    setBusy("projects", false);
  }
}

function handleProjectSelect(projectId) {
  const state = getState();
  const isCurrent = state.currentProjectId === projectId;

  if (isCurrent) {
    setCurrentProjectId(null);
    setSelectedProjectDetail(null);
    setProjectExpanded(projectId, false);
    setNewChatMenuOpen(false);
    return;
  }

  syncProjectSelection(projectId);
  setProjectExpanded(projectId, true);
  clearNotice("projects");
}

async function handleProjectDelete(projectId) {
  const state = getState();
  const project = state.projects.find((item) => item.id === projectId) || null;
  const confirmed = await openConfirmModal({
    title: "删除项目",
    body: project
      ? `确认删除项目“${project.name}”？项目内会话、消息和摘要会一起删除。`
      : "确认删除这个项目？项目内会话、消息和摘要会一起删除。",
    confirmLabel: "确认删除",
    confirmVariant: "danger",
  });
  if (!confirmed) {
    return;
  }
  const selectedSession = state.selectedSessionDetail;
  const deletingCurrentProject = state.currentProjectId === projectId;
  const deletingCurrentSession = selectedSession?.project_id === projectId;

  try {
    const response = await deleteProject(getBaseUrl(), projectId);
    if (deletingCurrentProject) {
      setCurrentProjectId(null);
      setSelectedProjectDetail(null);
      setNewChatMenuOpen(false);
    }
    if (deletingCurrentSession) {
      removeSessionData(selectedSession.id);
      clearSessionSelection();
    }
    showTransientNotice("projects", response.message || "Project deleted.", "warning");
    await refreshProjects({ silent: true });
    await refreshSessions({ silent: true });
  } catch (error) {
    setNotice("projects", `删除项目失败：${formatErrorMessage(error)}`, "danger");
  }
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
    setMessagesForSession(session.id, []);
    syncProjectSelection(session.project_id);
    setNewChatMenuOpen(false);
    showTransientNotice(
      "sessions",
      projectId === null ? "已创建未归属会话。" : "已在当前项目下创建新会话。",
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

async function handleSessionSelect(sessionId) {
  const state = getState();
  const session = state.sessions.find((item) => item.id === sessionId) || null;
  setCurrentSessionId(sessionId);
  setSelectedSessionDetail(session);
  clearNotice("chat");
  setNewChatMenuOpen(false);
  if (session) {
    syncProjectSelection(session.project_id);
  }
  await ensureSessionMessages(sessionId, { force: false });
}

async function handleRenameSession() {
  const state = getState();
  const session = state.selectedSessionDetail;
  if (!session) {
    setNotice("sessions", "当前没有选中会话。", "warning");
    return;
  }

  const nextTitle = window.prompt("输入新的会话标题", session.title || "");
  if (nextTitle === null) {
    return;
  }

  try {
    const updated = await updateSession(getBaseUrl(), session.id, {
      title: nextTitle,
    });
    setSelectedSessionDetail(updated);
    setNotice("sessions", `会话已改名为“${getSessionTitle(updated.title)}”。`, "success");
    await refreshSessions({ silent: true, loadMessages: false });
  } catch (error) {
    setNotice("sessions", `改名失败：${formatErrorMessage(error)}`, "danger");
  }
}

async function handleArchiveSession(sessionId) {
  try {
    const session = await archiveSession(getBaseUrl(), sessionId);
    setSelectedSessionDetail(session);
    setNotice("sessions", `会话 ${String(sessionId).slice(0, 10)} 已归档。`, "success");
    await refreshSessions({ silent: true, loadMessages: false });
  } catch (error) {
    setNotice("sessions", `归档失败：${formatErrorMessage(error)}`, "danger");
  }
}

async function handleDeleteSession(sessionId) {
  const state = getState();
  const deletingCurrentSession = state.currentSessionId === sessionId;
  const session = state.sessions.find((item) => item.id === sessionId) || state.selectedSessionDetail;
  const confirmed = await openConfirmModal({
    title: "删除会话",
    body: session?.title
      ? `确认删除会话“${getSessionTitle(session.title)}”？消息和摘要会一起删除。`
      : "确认删除这个会话？消息和摘要会一起删除。",
    confirmLabel: "确认删除",
    confirmVariant: "danger",
  });
  if (!confirmed) {
    return;
  }

  try {
    const response = await deleteSession(getBaseUrl(), sessionId);
    removeSessionData(sessionId);
    if (deletingCurrentSession) {
      clearSessionSelection();
    }
    showTransientNotice("sessions", response.message || "Session deleted.", "warning");
    clearNotice("chat");
    await refreshSessions({ silent: true, loadMessages: false });
  } catch (error) {
    setNotice("sessions", `删除失败：${formatErrorMessage(error)}`, "danger");
  }
}

async function handleMoveSession() {
  const state = getState();
  if (!state.currentSessionId) {
    setNotice("sessions", "当前没有选中会话。", "warning");
    return;
  }

  const moveSelect = document.querySelector("#moveProjectSelect");
  const rawValue = moveSelect?.value || "";
  if (!rawValue) {
    setNotice("sessions", "请先选择目标项目。", "warning");
    return;
  }

  const targetProjectId = parseOptionalProjectId(rawValue);

  try {
    const session = await moveSession(getBaseUrl(), state.currentSessionId, targetProjectId);
    setSelectedSessionDetail(session);
    syncProjectSelection(session.project_id);
    setNotice(
      "sessions",
      targetProjectId === null ? "会话已移出项目。" : "会话已移动到目标项目。",
      "success",
    );
    await refreshSessions({ silent: true, loadMessages: false });
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
    setNotice("chat", "请先从左侧选择一个会话。", "warning");
    return;
  }

  if (!canChatWithCurrentSelection()) {
    setNotice("chat", "当前会话已归档，请切换到其他会话。", "warning");
    return;
  }

  appendMessage(stateBeforeSend.currentSessionId, {
    role: "user",
    content: message,
    timestamp: Date.now(),
    sources: [],
  });
  resetComposer();
  clearNotice("chat");
  setBusy("chat", true);

  try {
    const response = await sendChat(getBaseUrl(), {
      message,
      session_id: stateBeforeSend.currentSessionId,
    });

    const nextSessionDetail = {
      id: response.session_id,
      title: response.title ?? stateBeforeSend.selectedSessionDetail?.title ?? null,
      project_id: stateBeforeSend.selectedSessionDetail?.project_id ?? null,
      status: "active",
      is_private: stateBeforeSend.selectedSessionDetail?.is_private || false,
      created_at: stateBeforeSend.selectedSessionDetail?.created_at,
      updated_at: new Date().toISOString(),
    };

    setCurrentSessionId(response.session_id);
    setSelectedSessionDetail(nextSessionDetail);
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
      `消息已发送，当前上下文解析结果为 ${getAccessModeLabel(response.context_scope)}。`,
      "success",
    );
    await refreshSessions({ silent: true, loadMessages: false });
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
  resizeComposer();
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

  const unassignedMoreToggle = event.target.closest("[data-unassigned-more-toggle]");
  if (unassignedMoreToggle) {
    toggleShowAllUnassigned();
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

  const projectEdit = event.target.closest("[data-project-edit]");
  if (projectEdit) {
    const projectId = Number.parseInt(projectEdit.dataset.projectEdit, 10);
    if (!Number.isNaN(projectId)) {
      openProjectEditModal(projectId);
    }
    return;
  }

  const projectDelete = event.target.closest("[data-project-delete]");
  if (projectDelete) {
    const projectId = Number.parseInt(projectDelete.dataset.projectDelete, 10);
    if (!Number.isNaN(projectId)) {
      handleProjectDelete(projectId);
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

  if (event.target.closest("#renameSessionButton")) {
    handleRenameSession();
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
    openProjectCreateModal();
    return;
  }

  if (
    event.target.closest("#closeProjectModalButton") ||
    event.target.closest("[data-close-project-modal]")
  ) {
    closeProjectModal();
    return;
  }

  if (
    event.target.closest("#closeConfirmModalButton") ||
    event.target.closest("#confirmCancelButton") ||
    event.target.closest("[data-close-confirm-modal]")
  ) {
    closeConfirmModal(false);
    return;
  }

  if (event.target.closest("#confirmAcceptButton")) {
    closeConfirmModal(true);
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
    getState().ui.newChatMenuOpen &&
    !event.target.closest("#newChatButton") &&
    !event.target.closest("#newChatMenu")
  ) {
    setNewChatMenuOpen(false);
  }
}

function handleGlobalKeydown(event) {
  if (event.key !== "Escape") {
    return;
  }

  if (pendingConfirmResolve) {
    closeConfirmModal(false);
    return;
  }

  if (!elements.projectModal.classList.contains("hidden")) {
    closeProjectModal();
  }
}
function wireEvents() {
  elements.newChatButton.addEventListener("click", handleNewChatClick);
  elements.projectForm.addEventListener("submit", handleProjectSubmit);
  elements.composerForm.addEventListener("submit", handleChatSubmit);
  elements.messageInput.addEventListener("keydown", handleComposerKeydown);
  elements.messageInput.addEventListener("input", resizeComposer);
  elements.quickChips.forEach((chip) => chip.addEventListener("click", handleQuickChipClick));
  document.addEventListener("click", handleGlobalClick);
  document.addEventListener("keydown", handleGlobalKeydown);
}

function renderAll(state) {
  renderManagement(state, elements);
  renderChat(state, elements);
}

async function bootstrap() {
  subscribe(renderAll);
  wireEvents();
  resizeComposer();
  await refreshHealth(true);
  await refreshProjects({ silent: true });
  await refreshSessions({ silent: true, forceMessages: true });
}

bootstrap();










