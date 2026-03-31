import { elements } from "./dom.js";
import { renderChat } from "./render-chat.js";
import { renderManagement } from "./render-management.js";
import { subscribe } from "./state.js";
import { createChatController } from "./controllers/chat-controller.js";
import { createProjectSessionController } from "./controllers/project-session-controller.js";
import { createNoticeModalHelpers } from "./helpers/notice-modal.js";
import { resetComposer, resizeComposer } from "./helpers/ui-helpers.js";
import { createAppRuntime } from "./app-runtime.js";
import { wireEvents } from "./wire-events.js";
import { sendChat } from "./api.js";

function renderAll(state) {
  renderManagement(state, elements);
  renderChat(state, elements);
}

export function createBootstrap() {
  const noticeModal = createNoticeModalHelpers({
    elements,
  });

  const managementController = createProjectSessionController({
    elements,
    showTransientNotice: noticeModal.showTransientNotice,
    openConfirmModal: noticeModal.openConfirmModal,
    closeConfirmModal: noticeModal.closeConfirmModal,
  });

  const runtime = createAppRuntime({
    syncSelectedSessionDetail: managementController.syncSelectedSessionDetail,
    ensureSessionMessages: managementController.ensureSessionMessages,
  });

  managementController.configureRuntime({
    getBaseUrl: runtime.getBaseUrl,
    getState: runtime.getState,
    refreshProjects: runtime.refreshProjects,
    refreshSessions: runtime.refreshSessions,
  });

  const chatController = createChatController({
    elements,
    getBaseUrl: runtime.getBaseUrl,
    getState: runtime.getState,
    canChatWithCurrentSelection: runtime.canChatWithCurrentSelection,
    refreshSessions: runtime.refreshSessions,
    resetComposer: () => resetComposer(elements),
    sendChat,
  });

  async function bootstrap() {
    subscribe(renderAll);
    wireEvents({
      elements,
      managementController,
      chatController,
      noticeModal,
    });
    resizeComposer(elements);
    await runtime.refreshHealth(true);
    await runtime.refreshProjects({ silent: true });
    await runtime.refreshSessions({ silent: true, forceMessages: true });
  }

  return { bootstrap };
}
