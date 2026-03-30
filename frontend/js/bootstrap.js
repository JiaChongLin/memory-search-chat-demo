import { getSession, healthCheck, listProjects, listSessions, normalizeBaseUrl, sendChat } from "./api.js";
import { elements } from "./dom.js";
import { renderChat } from "./render-chat.js";
import { renderManagement } from "./render-management.js";
import {
  clearNotice,
  getState,
  removeSessionData,
  setBackendBaseUrl,
  setBusy,
  setCurrentProjectId,
  setHealth,
  setProjects,
  setSelectedProjectDetail,
  setSelectedSessionDetail,
  setSessions,
  setNotice,
  subscribe,
} from "./state.js";
import { createChatController } from "./controllers/chat-controller.js";
import { createProjectSessionController } from "./controllers/project-session-controller.js";
import { createNoticeModalHelpers } from "./helpers/notice-modal.js";
import { formatErrorMessage, resetComposer, resizeComposer } from "./helpers/ui-helpers.js";

function getBaseUrl() {
  return normalizeBaseUrl(getState().backendBaseUrl);
}

function canChatWithCurrentSelection() {
  const state = getState();
  const session = state.selectedSessionDetail;
  if (!session) {
    return false;
  }
  return session.status !== "archived";
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

export function createBootstrap() {
  const noticeModal = createNoticeModalHelpers({
    elements,
    setNotice,
    clearNotice,
  });

  const managementController = createProjectSessionController({
    elements,
    getBaseUrl,
    getState,
    refreshProjects,
    refreshSessions,
    showTransientNotice: noticeModal.showTransientNotice,
    openConfirmModal: noticeModal.openConfirmModal,
    closeConfirmModal: noticeModal.closeConfirmModal,
  });

  async function refreshSessions(options = {}) {
    setBusy("sessions", true);
    try {
      const sessions = await listSessions(getBaseUrl());
      setSessions(sessions);
      await managementController.syncSelectedSessionDetail();

      const state = getState();
      if (state.currentSessionId && options.loadMessages !== false) {
        await managementController.ensureSessionMessages(state.currentSessionId, {
          force: Boolean(options.forceMessages),
        });
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

  const chatController = createChatController({
    elements,
    getBaseUrl,
    getState,
    canChatWithCurrentSelection,
    refreshSessions,
    resetComposer: () => resetComposer(elements),
    sendChat,
  });

  function renderAll(state) {
    renderManagement(state, elements);
    renderChat(state, elements);
  }

  function wireEvents() {
    elements.newChatButton.addEventListener("click", managementController.handleNewChatClick);
    elements.projectForm.addEventListener("submit", managementController.handleProjectSubmit);
    elements.composerForm.addEventListener("submit", chatController.handleChatSubmit);
    elements.messageInput.addEventListener("keydown", chatController.handleComposerKeydown);
    elements.messageInput.addEventListener("input", () => resizeComposer(elements));
    elements.quickChips.forEach((chip) => chip.addEventListener("click", chatController.handleQuickChipClick));
    document.addEventListener("click", managementController.handleGlobalClick);
    document.addEventListener("keydown", (event) =>
      noticeModal.handleGlobalKeydown(event, managementController.closeProjectModal),
    );
  }

  async function bootstrap() {
    subscribe(renderAll);
    wireEvents();
    resizeComposer(elements);
    await refreshHealth(true);
    await refreshProjects({ silent: true });
    await refreshSessions({ silent: true, forceMessages: true });
  }

  return { bootstrap };
}
