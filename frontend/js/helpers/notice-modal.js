import { clearNotice, setNotice } from "../state.js";

const NOTICE_AUTO_DISMISS_MS = 2600;
const NOTICE_FADE_MS = 320;

export function createNoticeModalHelpers({ elements }) {
  const noticeTimers = new Map();
  let pendingConfirmResolve = null;

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

  function handleGlobalKeydown(event, closeProjectModal) {
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

  return {
    showTransientNotice,
    closeConfirmModal,
    openConfirmModal,
    handleGlobalKeydown,
  };
}
