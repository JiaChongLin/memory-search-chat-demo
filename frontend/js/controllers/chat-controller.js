import { getAccessModeLabel } from "../labels.js";
import {
  appendMessage,
  setBusy,
  setChatDebug,
  setCurrentSessionId,
  setMemoryForSession,
  setNotice,
  setSelectedSessionDetail,
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
    setNotice("chat", null);
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

      showTransientNotice(
        "chat",
        `消息已发送，当前上下文解析结果为 ${getAccessModeLabel(response.context_scope)}。`,
        "success",
      );
      await refreshSessions({ silent: true, loadMessages: false });
    } catch (error) {
      appendMessage(stateBeforeSend.currentSessionId, {
        role: "system",
        content: `请求失败：${error instanceof Error ? error.message : "未知错误"}`,
        timestamp: Date.now(),
        sources: [],
      });
      setNotice(
        "chat",
        `聊天请求失败：${error instanceof Error ? error.message : "未知错误"}`,
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
