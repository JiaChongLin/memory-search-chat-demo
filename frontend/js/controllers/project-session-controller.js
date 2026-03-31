import { getAccessModeLabel, getPrivacyLabel, getSessionTitle } from "../labels.js";
import {
  archiveSession,
  createProject,
  createSession,
  deleteProject,
  deleteSession,
  getSession,
  getSessionMessages,
  getSessionSummary,
  moveSession,
  updateProject,
  updateSession,
} from "../api.js";
import {
  clearCurrentSessionSelection,
  clearNotice,
  getMessagesForSession,
  getState,
  getSummaryForSession,
  removeSessionData,
  setBusy,
  setCurrentProjectId,
  setCurrentSessionId,
  setMessagesForSession,
  setNewChatMenuOpen,
  setNotice,
  setProjectExpanded,
  setProjectModalState,
  setSelectedProjectDetail,
  setSelectedSessionDetail,
  setSummaryForSession,
  toggleProjectSessionExpansion,
  toggleShowAllProjects,
  toggleShowAllUnassigned,
  toggleSidebarSection,
} from "../state.js";
import {
  formatErrorMessage,
  mapApiMessage,
  parseOptionalProjectId,
  resetProjectForm,
} from "../helpers/ui-helpers.js";

export function createProjectSessionController({
  elements,
  showTransientNotice,
  openConfirmModal,
  closeConfirmModal,
  openInputModal,
  closeInputModal,
  handleInputModalSubmit,
}) {
  let getBaseUrl = () => "http://127.0.0.1:8000";
  let refreshProjects = async () => {};
  let refreshSessions = async () => {};

  function configureRuntime(runtime) {
    getBaseUrl = runtime.getBaseUrl;
    refreshProjects = runtime.refreshProjects;
    refreshSessions = runtime.refreshSessions;
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

  function closeProjectModal() {
    setProjectModalState({ isOpen: false, mode: "create", projectId: null });
    resetProjectForm(elements);
  }

  function openProjectCreateModal() {
    resetProjectForm(elements);
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

  async function ensureSessionSummary(sessionId, options = {}) {
    if (!sessionId) {
      return;
    }

    const force = Boolean(options.force);
    if (!force && getSummaryForSession(sessionId)) {
      return;
    }

    try {
      const payload = await getSessionSummary(getBaseUrl(), sessionId);
      setSummaryForSession(sessionId, payload.summary || null);
    } catch (error) {
      if (error.status === 404) {
        removeSessionData(sessionId);
        if (getState().currentSessionId === sessionId) {
          clearSessionSelection();
        }
        setNotice("sessions", "该会话不存在，无法读取内部 summary。", "warning");
        return;
      }
      setNotice("sessions", `加载会话 summary 失败：${formatErrorMessage(error)}`, "warning");
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

  async function createBlankSession(projectId = null, isPrivate = false) {
    try {
      setBusy("sessions", true);
      const session = await createSession(getBaseUrl(), {
        title: null,
        project_id: projectId,
        is_private: isPrivate,
      });
      setCurrentSessionId(session.id);
      setSelectedSessionDetail(session);
      setSummaryForSession(session.id, null);
      setMessagesForSession(session.id, []);
      syncProjectSelection(session.project_id);
      setNewChatMenuOpen(false);
      showTransientNotice(
        "sessions",
        isPrivate
          ? "已创建私密会话。"
          : projectId === null
            ? "已创建未归属会话。"
            : "已在当前项目下创建新会话。",
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
    setNewChatMenuOpen(!state.ui.newChatMenuOpen);
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
    await ensureSessionSummary(sessionId, { force: true });
    await ensureSessionMessages(sessionId, { force: false });
  }

  async function handleRenameSession() {
    const state = getState();
    const session = state.selectedSessionDetail;
    if (!session) {
      setNotice("sessions", "当前没有选中会话。", "warning");
      return;
    }

    const nextTitle = await openInputModal({
      title: "会话改名",
      body: "输入新的会话标题。留空时会恢复为未命名会话。",
      value: session.title || "",
      placeholder: "输入会话标题",
      confirmLabel: "保存标题",
    });
    if (nextTitle === null) {
      return;
    }

    try {
      const updated = await updateSession(getBaseUrl(), session.id, {
        title: nextTitle,
      });
      setSelectedSessionDetail(updated);
      showTransientNotice(
        "sessions",
        `会话已改名为“${getSessionTitle(updated.title)}”。`,
        "success",
      );
      await refreshSessions({ silent: true, loadMessages: false });
    } catch (error) {
      setNotice("sessions", `改名失败：${formatErrorMessage(error)}`, "danger");
    }
  }

  async function handleToggleSessionPrivacy() {
    const session = getState().selectedSessionDetail;
    if (!session) {
      setNotice("sessions", "当前没有选中会话。", "warning");
      return;
    }

    try {
      const updated = await updateSession(getBaseUrl(), session.id, {
        is_private: !session.is_private,
      });
      setSelectedSessionDetail(updated);
      showTransientNotice(
        "sessions",
        `会话已切换为${getPrivacyLabel(updated.is_private)}。后续上下文解析会立即按新规则生效。`,
        "success",
      );
      await refreshSessions({ silent: true, loadMessages: false });
    } catch (error) {
      setNotice("sessions", `更新私密性失败：${formatErrorMessage(error)}`, "danger");
    }
  }

  async function handleArchiveSession(sessionId) {
    try {
      const session = await archiveSession(getBaseUrl(), sessionId);
      setSelectedSessionDetail(session);
      showTransientNotice("sessions", `会话 ${String(sessionId).slice(0, 10)} 已归档。`, "success");
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
      showTransientNotice(
        "sessions",
        targetProjectId === null ? "会话已移出项目。" : "会话已移动到目标项目。",
        "success",
      );
      await refreshSessions({ silent: true, loadMessages: false });
    } catch (error) {
      setNotice("sessions", `移动失败：${formatErrorMessage(error)}`, "danger");
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

    const createSessionButton = event.target.closest("[data-create-session-scope]");
    if (createSessionButton) {
      const scope = createSessionButton.dataset.createSessionScope;
      const isPrivate = createSessionButton.dataset.createSessionPrivate === "true";
      const projectId = scope === "current-project" ? getState().currentProjectId : null;
      createBlankSession(projectId, isPrivate);
      return;
    }

    if (event.target.closest("#renameSessionButton")) {
      handleRenameSession();
      return;
    }

    if (event.target.closest("#toggleSessionPrivacyButton")) {
      handleToggleSessionPrivacy();
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

    if (
      event.target.closest("#closeInputModalButton") ||
      event.target.closest("#inputCancelButton") ||
      event.target.closest("[data-close-input-modal]")
    ) {
      closeInputModal(null);
      return;
    }

    if (event.target.closest("#inputAcceptButton")) {
      handleInputModalSubmit();
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

  return {
    configureRuntime,
    closeProjectModal,
    ensureSessionMessages,
    ensureSessionSummary,
    syncSelectedSessionDetail,
    handleProjectSubmit,
    handleNewChatClick,
    handleGlobalClick,
  };
}
