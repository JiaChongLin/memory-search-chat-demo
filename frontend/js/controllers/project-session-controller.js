import { getAccessModeLabel, getPrivacyLabel, getSessionTitle } from "../labels.js";
import {
  archiveSession,
  createProject,
  createProjectStableFact,
  createSession,
  deleteProject,
  deleteProjectStableFact,
  deleteSession,
  getSession,
  getSessionMessages,
  getSessionMemoryState,
  listProjectStableFacts,
  moveSession,
  updateProject,
  updateProjectStableFact,
  updateSession,
} from "../api.js";
import {
  clearCurrentSessionSelection,
  clearLatestTurnEditMode,
  clearNotice,
  clearStableFactsForProject,
  getMessagesForSession,
  getMemoryForSession,
  getStableFactsForProject,
  getState,
  removeSessionData,
  setBusy,
  setCurrentProjectId,
  setCurrentSessionId,
  setEditingStableFactId,
  setMessagesForSession,
  setNewChatMenuOpen,
  setNotice,
  setProjectExpanded,
  setProjectModalState,
  setSelectedProjectDetail,
  setSelectedSessionDetail,
  setMemoryForSession,
  setStableFactsForProject,
  toggleProjectSessionExpansion,
  toggleShowAllProjects,
  toggleShowAllUnassigned,
  toggleSidebarSection,
} from "../state.js";
import {
  formatErrorMessage,
  mapApiMessage,
  parseOptionalProjectId,
  resetComposer as resetComposerHelper,
  resetProjectForm,
} from "../helpers/ui-helpers.js";

export function createProjectSessionController({
  elements,
  resetComposer,
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
  const resetComposerView =
    typeof resetComposer === "function" ? resetComposer : () => resetComposerHelper(elements);

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

  function exitLatestTurnEditModeIfNeeded(options = {}) {
    const state = getState();
    const latestTurnEdit = state.ui.latestTurnEdit;
    const force = Boolean(options.force);
    const nextSessionId = options.nextSessionId ?? null;
    const shouldClear =
      force ||
      (latestTurnEdit?.active && latestTurnEdit.sessionId !== nextSessionId);

    if (!shouldClear) {
      return;
    }

    clearLatestTurnEditMode();
    resetComposerView();
    clearNotice("chat");
  }

  function clearSessionSelection() {
    clearCurrentSessionSelection();
    resetComposerView();
  }

  function resetStableFactEditor() {
    if (elements.stableFactInput) {
      elements.stableFactInput.value = "";
    }
    setEditingStableFactId(null);
  }

  function closeProjectModal() {
    setProjectModalState({
      isOpen: false,
      mode: "create",
      projectId: null,
      stableFactId: null,
    });
    resetProjectForm(elements);
    resetStableFactEditor();
  }

  function openProjectCreateModal() {
    resetProjectForm(elements);
    resetStableFactEditor();
    setProjectModalState({
      isOpen: true,
      mode: "create",
      projectId: null,
      stableFactId: null,
    });
    setNewChatMenuOpen(false);
  }

  async function loadProjectStableFacts(projectId, options = {}) {
    if (!projectId) {
      return [];
    }

    const force = Boolean(options.force);
    const cached = getStableFactsForProject(projectId);
    if (!force && cached.length) {
      return cached;
    }

    try {
      const facts = await listProjectStableFacts(getBaseUrl(), projectId, {
        include_archived: true,
      });
      setStableFactsForProject(projectId, facts);
      return facts;
    } catch (error) {
      setNotice("projects", `加载 stable facts 失败：${formatErrorMessage(error)}`, "warning");
      return cached;
    }
  }

  async function openProjectEditModal(projectId) {
    const state = getState();
    const project = state.projects.find((item) => item.id === projectId) || null;
    if (!project) {
      setNotice("projects", "目标项目不存在，无法编辑。", "warning");
      return;
    }

    elements.projectNameInput.value = project.name || "";
    elements.projectInstructionInput.value = project.instruction || "";
    elements.projectDescriptionInput.value = project.description || "";
    elements.projectAccessSelect.value = project.access_mode;
    resetStableFactEditor();
    setProjectModalState({
      isOpen: true,
      mode: "edit",
      projectId: project.id,
      stableFactId: null,
    });
    setNewChatMenuOpen(false);
    clearNotice("projects");
    await loadProjectStableFacts(project.id, { force: true });
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

  async function ensureSessionMemoryState(sessionId, options = {}) {
    if (!sessionId) {
      return;
    }

    const force = Boolean(options.force);
    if (!force && getMemoryForSession(sessionId)) {
      return;
    }

    try {
      const payload = await getSessionMemoryState(getBaseUrl(), sessionId);
      setMemoryForSession(sessionId, payload);
    } catch (error) {
      if (error.status === 404) {
        removeSessionData(sessionId);
        if (getState().currentSessionId === sessionId) {
          clearSessionSelection();
        }
        setNotice("sessions", "该会话不存在，无法读取会话记忆。", "warning");
        return;
      }
      setNotice("sessions", `加载会话记忆失败：${formatErrorMessage(error)}`, "warning");
    }
  }

  async function syncSelectedSessionDetail(options = {}) {
    const state = getState();
    const sessionId = options.sessionId ?? state.currentSessionId;
    if (!sessionId) {
      return null;
    }

    const matched = state.sessions.find((item) => item.id === sessionId) || null;
    if (matched && !options.forceRemote) {
      setSelectedSessionDetail(matched);
      return matched;
    }

    try {
      const detail = await getSession(getBaseUrl(), sessionId);
      setSelectedSessionDetail(detail);
      return detail;
    } catch (error) {
      if (error.status === 404) {
        removeSessionData(sessionId);
        if (getState().currentSessionId === sessionId) {
          clearSessionSelection();
        }
        return null;
      }
      setNotice("sessions", `\u540c\u6b65\u4f1a\u8bdd\u8be6\u60c5\u5931\u8d25\uff1a${formatErrorMessage(error)}`, "warning");
      return matched;
    }
  }

  async function handleProjectSubmit(event) {
    event.preventDefault();

    const state = getState();
    const payload = {
      name: elements.projectNameInput.value.trim(),
      instruction: elements.projectInstructionInput.value.trim() || null,
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

  async function handleStableFactSubmit() {
    const state = getState();
    const projectId = state.ui.editingProjectId;
    if (state.ui.projectModalMode !== "edit" || !projectId) {
      setNotice("projects", "请先创建项目，再管理 stable facts。", "warning");
      return;
    }

    const content = elements.stableFactInput?.value.trim() || "";
    if (!content) {
      setNotice("projects", "stable fact 内容不能为空。", "warning");
      return;
    }

    try {
      setBusy("projects", true);
      if (state.ui.editingStableFactId) {
        await updateProjectStableFact(getBaseUrl(), projectId, state.ui.editingStableFactId, {
          content,
        });
        showTransientNotice("projects", "stable fact 已更新。", "success");
      } else {
        await createProjectStableFact(getBaseUrl(), projectId, { content });
        showTransientNotice("projects", "stable fact 已保存。", "success");
      }
      resetStableFactEditor();
      await loadProjectStableFacts(projectId, { force: true });
    } catch (error) {
      setNotice("projects", `保存 stable fact 失败：${formatErrorMessage(error)}`, "danger");
    } finally {
      setBusy("projects", false);
    }
  }

  function handleStableFactEdit(factId) {
    const state = getState();
    const projectId = state.ui.editingProjectId;
    const facts = getStableFactsForProject(projectId);
    const fact = facts.find((item) => item.id === factId) || null;
    if (!fact) {
      setNotice("projects", "目标 stable fact 不存在。", "warning");
      return;
    }

    if (elements.stableFactInput) {
      elements.stableFactInput.value = fact.content;
      elements.stableFactInput.focus();
    }
    setEditingStableFactId(fact.id);
    clearNotice("projects");
  }

  function handleStableFactCancelEdit() {
    resetStableFactEditor();
    clearNotice("projects");
  }

  async function handleStableFactToggle(factId) {
    const state = getState();
    const projectId = state.ui.editingProjectId;
    if (!projectId) {
      return;
    }

    const facts = getStableFactsForProject(projectId);
    const fact = facts.find((item) => item.id === factId) || null;
    if (!fact) {
      setNotice("projects", "目标 stable fact 不存在。", "warning");
      return;
    }

    const nextStatus = fact.status === "active" ? "archived" : "active";
    try {
      setBusy("projects", true);
      await updateProjectStableFact(getBaseUrl(), projectId, factId, { status: nextStatus });
      if (state.ui.editingStableFactId === factId && nextStatus === "archived") {
        resetStableFactEditor();
      }
      showTransientNotice(
        "projects",
        nextStatus === "active" ? "stable fact 已重新启用。" : "stable fact 已停用。",
        "success",
      );
      await loadProjectStableFacts(projectId, { force: true });
    } catch (error) {
      setNotice("projects", `更新 stable fact 状态失败：${formatErrorMessage(error)}`, "danger");
    } finally {
      setBusy("projects", false);
    }
  }

  async function handleStableFactDelete(factId) {
    const state = getState();
    const projectId = state.ui.editingProjectId;
    if (!projectId) {
      return;
    }

    const facts = getStableFactsForProject(projectId);
    const fact = facts.find((item) => item.id === factId) || null;
    const confirmed = await openConfirmModal({
      title: "删除 stable fact",
      body: fact
        ? `确认删除这条 stable fact？\n\n${fact.content}`
        : "确认删除这条 stable fact？",
      confirmLabel: "确认删除",
      confirmVariant: "danger",
    });
    if (!confirmed) {
      return;
    }

    try {
      setBusy("projects", true);
      await deleteProjectStableFact(getBaseUrl(), projectId, factId);
      if (state.ui.editingStableFactId === factId) {
        resetStableFactEditor();
      }
      showTransientNotice("projects", "stable fact 已删除。", "warning");
      await loadProjectStableFacts(projectId, { force: true });
    } catch (error) {
      setNotice("projects", `删除 stable fact 失败：${formatErrorMessage(error)}`, "danger");
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
        ? `确认删除项目“${project.name}”？项目内会话、消息、派生记忆和 stable facts 会一起删除。`
        : "确认删除这个项目？项目内会话、消息、派生记忆和 stable facts 会一起删除。",
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
      clearStableFactsForProject(projectId);
      if (deletingCurrentProject) {
        setCurrentProjectId(null);
        setSelectedProjectDetail(null);
        setNewChatMenuOpen(false);
      }
      if (deletingCurrentSession) {
        exitLatestTurnEditModeIfNeeded({ force: true });
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
      exitLatestTurnEditModeIfNeeded({ force: true });
      setBusy("sessions", true);
      const session = await createSession(getBaseUrl(), {
        title: null,
        project_id: projectId,
        is_private: isPrivate,
      });
      setCurrentSessionId(session.id);
      setSelectedSessionDetail(session);
      setMemoryForSession(session.id, null);
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
    exitLatestTurnEditModeIfNeeded({ nextSessionId: sessionId });
    const session = state.sessions.find((item) => item.id === sessionId) || null;
    setCurrentSessionId(sessionId);
    setSelectedSessionDetail(session);
    clearNotice("chat");
    setNewChatMenuOpen(false);
    if (session) {
      syncProjectSelection(session.project_id);
    }

    const detail = await syncSelectedSessionDetail({
      sessionId,
      forceRemote: true,
    });
    if (detail) {
      syncProjectSelection(detail.project_id);
    }

    await Promise.all([
      ensureSessionMemoryState(sessionId, { force: true }),
      ensureSessionMessages(sessionId, { force: true }),
    ]);
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
      exitLatestTurnEditModeIfNeeded({ force: true });
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
        ? `确认删除会话“${getSessionTitle(session.title)}”？消息和派生记忆会一起删除。`
        : "确认删除这个会话？消息和派生记忆会一起删除。",
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
        exitLatestTurnEditModeIfNeeded({ force: true });
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

    const stableFactEdit = event.target.closest("[data-stable-fact-edit]");
    if (stableFactEdit) {
      const factId = Number.parseInt(stableFactEdit.dataset.stableFactEdit, 10);
      if (!Number.isNaN(factId)) {
        handleStableFactEdit(factId);
      }
      return;
    }

    const stableFactToggle = event.target.closest("[data-stable-fact-toggle]");
    if (stableFactToggle) {
      const factId = Number.parseInt(stableFactToggle.dataset.stableFactToggle, 10);
      if (!Number.isNaN(factId)) {
        handleStableFactToggle(factId);
      }
      return;
    }

    const stableFactDelete = event.target.closest("[data-stable-fact-delete]");
    if (stableFactDelete) {
      const factId = Number.parseInt(stableFactDelete.dataset.stableFactDelete, 10);
      if (!Number.isNaN(factId)) {
        handleStableFactDelete(factId);
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

    if (event.target.closest("#stableFactSubmitButton")) {
      handleStableFactSubmit();
      return;
    }

    if (event.target.closest("#stableFactCancelButton")) {
      handleStableFactCancelEdit();
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
    ensureSessionMemoryState,
    syncSelectedSessionDetail,
    handleProjectSubmit,
    handleNewChatClick,
    handleGlobalClick,
  };
}
