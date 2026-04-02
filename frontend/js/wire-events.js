import { resizeComposer } from "./helpers/ui-helpers.js";

export function wireEvents({
  elements,
  managementController,
  chatController,
  noticeModal,
}) {
  elements.newChatButton.addEventListener("click", managementController.handleNewChatClick);
  elements.projectForm.addEventListener("submit", managementController.handleProjectSubmit);
  elements.composerForm.addEventListener("submit", chatController.handleChatSubmit);
  elements.messageInput.addEventListener("keydown", chatController.handleComposerKeydown);
  elements.messageInput.addEventListener("input", () => resizeComposer(elements));
  if (elements.cancelLatestTurnEditButton) {
    elements.cancelLatestTurnEditButton.addEventListener(
      "click",
      chatController.handleCancelLatestTurnEdit,
    );
  }
  elements.quickChips.forEach((chip) =>
    chip.addEventListener("click", chatController.handleQuickChipClick),
  );
  document.addEventListener("click", managementController.handleGlobalClick);
  document.addEventListener("click", chatController.handleGlobalClick);
  document.addEventListener("keydown", (event) =>
    noticeModal.handleGlobalKeydown(event, managementController.closeProjectModal),
  );
}
