import { getAccessModeLabel } from "../labels.js";
import {
  appendMessage,
  clearLatestTurnEditMode,
  getMessagesForCurrentSession,
  removeMessage,
  setBusy,
  setChatDebug,
  setCurrentSessionId,
  setLatestTurnEditMode,
  setMemoryForSession,
  setNotice,
  updateLatestTurnEditDraft,
} from "../state.js";
import {
  buildAssistantDebug,
  getLatestTurnIndexes,
  resetComposer as resetComposerHelper,
} from "../helpers/ui-helpers.js";

const TEXT = {
  selectSession: "\u8bf7\u5148\u4ece\u5de6\u4fa7\u9009\u62e9\u4e00\u4e2a\u4f1a\u8bdd\u3002",
  archivedSession: "\u5f53\u524d\u4f1a\u8bdd\u5df2\u5f52\u6863\uff0c\u8bf7\u5207\u6362\u5230\u5176\u4ed6\u4f1a\u8bdd\u3002",
  unknownError: "\u672a\u77e5\u9519\u8bef",
  sendFailed: "\u804a\u5929\u8bf7\u6c42\u5931\u8d25\uff1a",
  contextResolved(responseScope) {
    return `\u6d88\u606f\u5df2\u53d1\u9001\uff0c\u5f53\u524d\u4e0a\u4e0b\u6587\u89e3\u6790\u7ed3\u679c\u4e3a ${getAccessModeLabel(responseScope)}\u3002`;
  },
  latestTurnEdited: "\u6700\u65b0\u4e00\u8f6e\u5df2\u66ff\u6362\uff0c\u5e76\u91cd\u65b0\u751f\u6210\u56de\u590d\u3002",
  latestTurnEditFailed: "\u7f16\u8f91\u6700\u65b0\u4e00\u8f6e\u5931\u8d25\uff1a",
  latestTurnEditPending:
    "\u8bf7\u5148\u5728\u6d88\u606f\u5361\u7247\u5185\u4fdd\u5b58\u6216\u53d6\u6d88\u5f53\u524d\u7f16\u8f91\uff0c\u518d\u53d1\u9001\u65b0\u6d88\u606f\u3002",
  onlyLatestTurn: "\u53ea\u6709\u6700\u65b0\u4e00\u8f6e\u6d88\u606f\u652f\u6301\u8fd9\u91cc\u7684\u5feb\u6377\u64cd\u4f5c\u3002",
  latestTurnEditConflict:
    "\u5f53\u524d\u4f1a\u8bdd\u6700\u540e\u4e24\u6761\u6d88\u606f\u4e0d\u662f\u201c\u7528\u6237 -> \u52a9\u624b\u201d\u7684\u6700\u65b0\u4e00\u8f6e\uff0c\u65e0\u6cd5\u7f16\u8f91\u3002\u8bf7\u5237\u65b0\u4f1a\u8bdd\u540e\u518d\u8bd5\u3002",
  noCopyContent: "\u6ca1\u6709\u53ef\u590d\u5236\u7684\u6d88\u606f\u5185\u5bb9\u3002",
  clipboardUnavailable: "\u5f53\u524d\u73af\u5883\u4e0d\u652f\u6301\u526a\u8d34\u677f\u590d\u5236\u3002",
  copied: "\u6d88\u606f\u5df2\u590d\u5236\u5230\u526a\u8d34\u677f\u3002",
  copyFailed: "\u590d\u5236\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u6d4f\u89c8\u5668\u526a\u8d34\u677f\u6743\u9650\u3002",
  onlyLatestUserEditable: "\u53ea\u6709\u6700\u65b0\u7528\u6237\u6d88\u606f\u53ef\u4ee5\u7f16\u8f91\u3002",
  archivedCannotEdit: "\u5f52\u6863\u4f1a\u8bdd\u4e0d\u80fd\u7f16\u8f91\u6700\u65b0\u4e00\u8f6e\u3002",
  unchangedLatestTurnEdit:
    "\u8bf7\u5148\u4fee\u6539\u6d88\u606f\u5185\u5bb9\uff0c\u518d\u53d1\u9001\u7f16\u8f91\u540e\u7684\u6700\u65b0\u4e00\u8f6e\u3002",
  noLatestTurnToRegenerate: "\u5f53\u524d\u4f1a\u8bdd\u6ca1\u6709\u53ef\u91cd\u7b54\u7684\u6700\u65b0\u4e00\u8f6e\u3002",
  archivedCannotRegenerate: "\u5f52\u6863\u4f1a\u8bdd\u4e0d\u80fd\u91cd\u7b54\u6700\u65b0\u4e00\u8f6e\u3002",
  regenerateSuccess: "\u6700\u65b0\u52a9\u624b\u56de\u590d\u5df2\u66ff\u6362\u4e3a\u65b0\u7684\u91cd\u7b54\u7ed3\u679c\u3002",
  regenerateFailed: "\u91cd\u7b54\u6700\u65b0\u4e00\u8f6e\u5931\u8d25\uff1a",
  regenerateConflict:
    "\u5f53\u524d\u4f1a\u8bdd\u6700\u540e\u4e24\u6761\u6d88\u606f\u4e0d\u662f\u201c\u7528\u6237 -> \u52a9\u624b\u201d\u7684\u6700\u65b0\u4e00\u8f6e\uff0c\u65e0\u6cd5\u91cd\u7b54\u3002\u8bf7\u5237\u65b0\u4f1a\u8bdd\u540e\u518d\u8bd5\u3002",
};

function buildApiUrl(baseUrl, path) {
  return new URL(path, `${baseUrl.replace(/\/+$/, "")}/`).toString();
}

async function requestLatestTurn(baseUrl, path, payload = null) {
  const response = await fetch(buildApiUrl(baseUrl, path), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: payload ? JSON.stringify(payload) : undefined,
  });

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const error = new Error(data?.error?.message || `HTTP ${response.status}`);
    error.status = response.status;
    error.payload = data;
    throw error;
  }

  return data;
}

function latestTurnEditFallback(baseUrl, sessionId, payload) {
  return requestLatestTurn(baseUrl, `/api/sessions/${sessionId}/latest-turn/edit`, payload);
}

function latestTurnRegenerateFallback(baseUrl, sessionId) {
  return requestLatestTurn(baseUrl, `/api/sessions/${sessionId}/latest-turn/regenerate`);
}

export function createChatController({
  elements,
  getBaseUrl,
  getState,
  canChatWithCurrentSelection,
  refreshSessions,
  resetComposer,
  sendChat,
  latestTurnEdit: latestTurnEditHandler,
  latestTurnRegenerate: latestTurnRegenerateHandler,
  showTransientNotice,
}) {
  const resetComposerView =
    typeof resetComposer === "function" ? resetComposer : () => resetComposerHelper(elements);
  const latestTurnEditRequest =
    typeof latestTurnEditHandler === "function"
      ? latestTurnEditHandler
      : latestTurnEditFallback;
  const latestTurnRegenerateRequest =
    typeof latestTurnRegenerateHandler === "function"
      ? latestTurnRegenerateHandler
      : latestTurnRegenerateFallback;

  function isEditingLatestTurnForState(state) {
    return Boolean(
      state.ui.latestTurnEdit?.active &&
        state.ui.latestTurnEdit.sessionId &&
        state.ui.latestTurnEdit.sessionId === state.currentSessionId,
    );
  }

  function getLatestTurnForCurrentSession() {
    const state = getState();
    const sessionId = state.currentSessionId;
    const messages = getMessagesForCurrentSession();
    const latestTurn = getLatestTurnIndexes(messages);

    return {
      state,
      sessionId,
      messages,
      ...latestTurn,
    };
  }

  function getInlineEditState() {
    const state = getState();
    const editState = state.ui.latestTurnEdit || {};
    const isCurrentSessionEdit =
      Boolean(editState.active) && editState.sessionId === state.currentSessionId;

    return {
      state,
      active: isCurrentSessionEdit,
      sessionId: isCurrentSessionEdit ? editState.sessionId : null,
      messageIndex: isCurrentSessionEdit ? Number(editState.messageIndex) : -1,
      originalContent: isCurrentSessionEdit ? editState.originalContent || "" : "",
      draft: isCurrentSessionEdit ? editState.draft || "" : "",
    };
  }

  function focusInlineEditor(messageIndex) {
    window.requestAnimationFrame(() => {
      const input = document.querySelector(
        `[data-latest-turn-edit-input="${String(messageIndex)}"]`,
      );
      if (!(input instanceof HTMLTextAreaElement)) {
        return;
      }

      input.focus({ preventScroll: true });
      input.setSelectionRange(input.value.length, input.value.length);
      input.style.height = "auto";
      input.style.height = `${input.scrollHeight}px`;
    });
  }

  function restoreComposerValue(message) {
    elements.messageInput.value = message;
    elements.messageInput.dispatchEvent(new Event("input", { bubbles: true }));
    elements.messageInput.focus();
  }

  function exitLatestTurnEditMode() {
    clearLatestTurnEditMode();
  }

  async function applyChatResponse(response, successMessage) {
    setCurrentSessionId(response.session_id);
    setMemoryForSession(response.session_id, {
      working_memory: response.working_memory || null,
      session_digest: response.session_digest || null,
    });
    setChatDebug(response.session_id, buildAssistantDebug(response));
    exitLatestTurnEditMode();

    await refreshSessions({
      silent: true,
      forceMessages: true,
      forceSummary: true,
    });

    showTransientNotice(
      "chat",
      successMessage || TEXT.contextResolved(response.context_scope),
      "success",
    );
  }

  async function handleStandardSubmit(message, stateBeforeSend) {
    const optimisticMessage = {
      role: "user",
      content: message,
      timestamp: Date.now(),
      sources: [],
    };

    appendMessage(stateBeforeSend.currentSessionId, optimisticMessage);
    resetComposerView();
    setNotice("chat", null);
    setBusy("chat", true);

    try {
      const response = await sendChat(getBaseUrl(), {
        message,
        session_id: stateBeforeSend.currentSessionId,
      });

      appendMessage(response.session_id, {
        role: "assistant",
        content: response.reply,
        timestamp: Date.now(),
        sources: response.sources || [],
        debug: buildAssistantDebug(response),
      });

      await applyChatResponse(response, TEXT.contextResolved(response.context_scope));
    } catch (error) {
      removeMessage(stateBeforeSend.currentSessionId, optimisticMessage);
      restoreComposerValue(message);
      setNotice(
        "chat",
        `${TEXT.sendFailed}${error instanceof Error ? error.message : TEXT.unknownError}`,
        "danger",
      );
    } finally {
      setBusy("chat", false);
    }
  }

  async function handleLatestTurnEditSubmit(message, stateBeforeSend, options = {}) {
    const messageIndex = Number(options.messageIndex ?? -1);
    let shouldRestoreInlineFocus = false;
    setNotice("chat", null);
    setBusy("chat", true);

    try {
      const response = await latestTurnEditRequest(getBaseUrl(), stateBeforeSend.currentSessionId, {
        message,
      });
      await applyChatResponse(response, TEXT.latestTurnEdited);
    } catch (error) {
      shouldRestoreInlineFocus = messageIndex >= 0;
      setNotice(
        "chat",
        error?.status === 409
          ? TEXT.latestTurnEditConflict
          : `${TEXT.latestTurnEditFailed}${error instanceof Error ? error.message : TEXT.unknownError}`,
        error?.status === 409 ? "warning" : "danger",
      );
    } finally {
      setBusy("chat", false);
      if (shouldRestoreInlineFocus) {
        focusInlineEditor(messageIndex);
      }
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
      setNotice("chat", TEXT.selectSession, "warning");
      return;
    }

    if (!canChatWithCurrentSelection()) {
      setNotice("chat", TEXT.archivedSession, "warning");
      return;
    }

    if (isEditingLatestTurnForState(stateBeforeSend)) {
      setNotice("chat", TEXT.latestTurnEditPending, "warning");
      return;
    }

    await handleStandardSubmit(message, stateBeforeSend);
  }

  function handleQuickChipClick(event) {
    if (getState().ui.latestTurnEdit?.active) {
      setNotice("chat", TEXT.latestTurnEditPending, "warning");
      return;
    }

    const chip = event.target.closest(".quick-chip");
    if (!chip) {
      return;
    }

    elements.messageInput.value = chip.dataset.prompt || "";
    elements.messageInput.dispatchEvent(new Event("input", { bubbles: true }));
    elements.messageInput.focus();
  }

  function handleComposerKeydown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      elements.composerForm.requestSubmit();
    }
  }

  function handleCancelLatestTurnEdit() {
    exitLatestTurnEditMode();
    setNotice("chat", null);
  }

  async function handleCopyMessage(messageIndex) {
    const { messages } = getLatestTurnForCurrentSession();
    const message = messages[messageIndex];
    if (!message?.content) {
      setNotice("chat", TEXT.noCopyContent, "warning");
      return;
    }

    if (!navigator.clipboard?.writeText) {
      setNotice("chat", TEXT.clipboardUnavailable, "warning");
      return;
    }

    try {
      await navigator.clipboard.writeText(message.content);
      showTransientNotice("chat", TEXT.copied, "success");
    } catch {
      setNotice("chat", TEXT.copyFailed, "warning");
    }
  }

  function handleStartLatestTurnEdit(messageIndex) {
    const { state, sessionId, messages, latestUserIndex } = getLatestTurnForCurrentSession();
    if (!sessionId || messageIndex !== latestUserIndex) {
      setNotice("chat", TEXT.onlyLatestUserEditable, "warning");
      return;
    }
    if (state.selectedSessionDetail?.status === "archived") {
      setNotice("chat", TEXT.archivedCannotEdit, "warning");
      return;
    }

    const message = messages[messageIndex];
    setLatestTurnEditMode(sessionId, messageIndex, message?.content || "");
    focusInlineEditor(messageIndex);
    setNotice("chat", null);
  }

  async function handleInlineLatestTurnEditSubmit(messageIndex) {
    const inlineEditState = getInlineEditState();
    if (!inlineEditState.active || inlineEditState.messageIndex !== messageIndex) {
      setNotice("chat", TEXT.onlyLatestUserEditable, "warning");
      return;
    }

    const nextMessage = inlineEditState.draft;
    const hasChanged = nextMessage !== inlineEditState.originalContent;
    if (!hasChanged || !nextMessage.trim()) {
      setNotice("chat", TEXT.unchangedLatestTurnEdit, "warning");
      return;
    }

    await handleLatestTurnEditSubmit(nextMessage.trim(), inlineEditState.state, {
      messageIndex,
    });
  }

  async function handleLatestTurnRegenerate() {
    const { state, sessionId, hasLatestTurn } = getLatestTurnForCurrentSession();
    if (!sessionId || !hasLatestTurn) {
      setNotice("chat", TEXT.noLatestTurnToRegenerate, "warning");
      return;
    }
    if (isEditingLatestTurnForState(state)) {
      setNotice("chat", TEXT.latestTurnEditPending, "warning");
      return;
    }
    if (state.selectedSessionDetail?.status === "archived") {
      setNotice("chat", TEXT.archivedCannotRegenerate, "warning");
      return;
    }

    setNotice("chat", null);
    setBusy("chat", true);
    try {
      const response = await latestTurnRegenerateRequest(getBaseUrl(), sessionId);
      await applyChatResponse(response, TEXT.regenerateSuccess);
    } catch (error) {
      setNotice(
        "chat",
        error?.status === 409
          ? TEXT.regenerateConflict
          : `${TEXT.regenerateFailed}${error instanceof Error ? error.message : TEXT.unknownError}`,
        error?.status === 409 ? "warning" : "danger",
      );
    } finally {
      setBusy("chat", false);
    }
  }

  function handleGlobalClick(event) {
    const actionButton = event.target.closest("[data-message-action]");
    if (!actionButton) {
      return;
    }

    const messageIndex = Number.parseInt(actionButton.dataset.messageIndex || "-1", 10);
    if (Number.isNaN(messageIndex)) {
      return;
    }

    const action = actionButton.dataset.messageAction;
    if (action === "copy-message") {
      handleCopyMessage(messageIndex);
      return;
    }
    if (action === "cancel-edit-latest-turn") {
      handleCancelLatestTurnEdit();
      return;
    }
    if (action === "submit-edit-latest-turn") {
      handleInlineLatestTurnEditSubmit(messageIndex);
      return;
    }
    if (action === "edit-latest-turn") {
      handleStartLatestTurnEdit(messageIndex);
      return;
    }
    if (action === "regenerate-latest-turn") {
      handleLatestTurnRegenerate();
    }
  }

  function handleGlobalInput(event) {
    const input = event.target.closest("[data-latest-turn-edit-input]");
    if (!(input instanceof HTMLTextAreaElement)) {
      return;
    }

    input.style.height = "auto";
    input.style.height = `${input.scrollHeight}px`;
    updateLatestTurnEditDraft(input.value);

    const inlineEditState = getInlineEditState();
    const submitButton = input
      .closest(".message-inline-editor")
      ?.querySelector('[data-message-action="submit-edit-latest-turn"]');
    if (!(submitButton instanceof HTMLButtonElement)) {
      return;
    }

    const canSubmit =
      inlineEditState.active &&
      !inlineEditState.state.busy.chat &&
      inlineEditState.state.selectedSessionDetail?.status !== "archived" &&
      Boolean(input.value.trim()) &&
      input.value !== inlineEditState.originalContent;

    submitButton.disabled = !canSubmit;
    submitButton.title = canSubmit ? "发送编辑后的最新用户消息" : "请先修改内容后再发送";
    submitButton.setAttribute("aria-label", submitButton.title);
  }

  return {
    handleChatSubmit,
    handleQuickChipClick,
    handleComposerKeydown,
    handleCancelLatestTurnEdit,
    handleGlobalInput,
    handleGlobalClick,
  };
}
