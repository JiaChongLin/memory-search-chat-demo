import { getAccessModeLabel } from "../labels.js";
import {
  appendMessage,
  removeMessage,
  setBusy,
  setChatDebug,
  setCurrentSessionId,
  setMemoryForSession,
  setNotice,
} from "../state.js";
import { buildAssistantDebug } from "../helpers/ui-helpers.js";

export function createChatController({
  elements,
  getBaseUrl,
  getState,
  canChatWithCurrentSelection,
  refreshSessions,
  resetComposer,
  sendChat,
  showTransientNotice,
}) {
  async function handleChatSubmit(event) {
    event.preventDefault();

    const message = elements.messageInput.value.trim();
    if (!message) {
      return;
    }

    const stateBeforeSend = getState();
    if (!stateBeforeSend.currentSessionId) {
      setNotice("chat", "\u8bf7\u5148\u4ece\u5de6\u4fa7\u9009\u62e9\u4e00\u4e2a\u4f1a\u8bdd\u3002", "warning");
      return;
    }

    if (!canChatWithCurrentSelection()) {
      setNotice("chat", "\u5f53\u524d\u4f1a\u8bdd\u5df2\u5f52\u6863\uff0c\u8bf7\u5207\u6362\u5230\u5176\u4ed6\u4f1a\u8bdd\u3002", "warning");
      return;
    }

    const optimisticMessage = {
      role: "user",
      content: message,
      timestamp: Date.now(),
      sources: [],
    };

    appendMessage(stateBeforeSend.currentSessionId, optimisticMessage);
    resetComposer();
    setNotice("chat", null);
    setBusy("chat", true);

    try {
      const response = await sendChat(getBaseUrl(), {
        message,
        session_id: stateBeforeSend.currentSessionId,
      });

      setCurrentSessionId(response.session_id);
      setMemoryForSession(response.session_id, {
        working_memory: response.working_memory || null,
        session_digest: response.session_digest || null,
      });
      setChatDebug(response.session_id, buildAssistantDebug(response));

      appendMessage(response.session_id, {
        role: "assistant",
        content: response.reply,
        timestamp: Date.now(),
        sources: response.sources || [],
        debug: buildAssistantDebug(response),
      });

      await refreshSessions({
        silent: true,
        forceMessages: true,
        forceSummary: true,
      });

      showTransientNotice(
        "chat",
        `\u6d88\u606f\u5df2\u53d1\u9001\uff0c\u5f53\u524d\u4e0a\u4e0b\u6587\u89e3\u6790\u7ed3\u679c\u4e3a ${getAccessModeLabel(response.context_scope)}\u3002`,
        "success",
      );
    } catch (error) {
      removeMessage(stateBeforeSend.currentSessionId, optimisticMessage);
      elements.messageInput.value = message;
      elements.messageInput.dispatchEvent(new Event("input", { bubbles: true }));
      elements.messageInput.focus();
      setNotice(
        "chat",
        `\u804a\u5929\u8bf7\u6c42\u5931\u8d25\uff1a${error instanceof Error ? error.message : "\u672a\u77e5\u9519\u8bef"}`,
        "danger",
      );
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
    elements.messageInput.dispatchEvent(new Event("input", { bubbles: true }));
    elements.messageInput.focus();
  }

  function handleComposerKeydown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      elements.composerForm.requestSubmit();
    }
  }

  return {
    handleChatSubmit,
    handleQuickChipClick,
    handleComposerKeydown,
  };
}
