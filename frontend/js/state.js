import {
  DEFAULT_BACKEND_BASE_URL,
  loadPersistedState,
  persistStateSnapshot,
} from "./storage.js";

export const DRAFT_SESSION_KEY = "__draft__";

const persisted = loadPersistedState();
const listeners = new Set();

function toBooleanMap(values) {
  const result = {};
  for (const value of values || []) {
    result[String(value)] = true;
  }
  return result;
}

const state = {
  backendBaseUrl: DEFAULT_BACKEND_BASE_URL,
  currentProjectId: persisted.currentProjectId,
  currentSessionId: persisted.currentSessionId,
  memoryMap: {},
  messageMap: {},
  stableFactMap: {},
  chatDebugMap: {},
  projects: [],
  sessions: [],
  selectedProjectDetail: null,
  selectedSessionDetail: null,
  health: {
    status: "idle",
    label: "未检查",
    environment: "unknown",
  },
  notices: {
    global: null,
    projects: null,
    sessions: null,
    chat: null,
  },
  busy: {
    health: false,
    projects: false,
    sessions: false,
    chat: false,
  },
  ui: {
    sidebar: {
      collapsedSections: {
        projects: Boolean(persisted.sidebar?.collapsedSections?.projects),
        unassigned: Boolean(persisted.sidebar?.collapsedSections?.unassigned),
      },
      showAllProjects: Boolean(persisted.sidebar?.showAllProjects),
      showAllUnassigned: Boolean(persisted.sidebar?.showAllUnassigned),
      expandedProjectIds: toBooleanMap(persisted.sidebar?.expandedProjectIds),
      expandedProjectSessionIds: toBooleanMap(
        persisted.sidebar?.expandedProjectSessionIds,
      ),
    },
    projectModalOpen: false,
    projectModalMode: "create",
    editingProjectId: null,
    editingStableFactId: null,
    newChatMenuOpen: false,
    latestTurnEdit: {
      active: false,
      sessionId: null,
      messageIndex: -1,
      originalContent: "",
      draft: "",
    },
  },
};

function buildPersistedSidebarState() {
  return {
    collapsedSections: {
      ...state.ui.sidebar.collapsedSections,
    },
    showAllProjects: state.ui.sidebar.showAllProjects,
    showAllUnassigned: state.ui.sidebar.showAllUnassigned,
    expandedProjectIds: Object.entries(state.ui.sidebar.expandedProjectIds)
      .filter(([, value]) => value)
      .map(([key]) => Number.parseInt(key, 10))
      .filter((value) => !Number.isNaN(value)),
    expandedProjectSessionIds: Object.entries(state.ui.sidebar.expandedProjectSessionIds)
      .filter(([, value]) => value)
      .map(([key]) => Number.parseInt(key, 10))
      .filter((value) => !Number.isNaN(value)),
  };
}


function resetLatestTurnEditState(draft) {
  draft.ui.latestTurnEdit.active = false;
  draft.ui.latestTurnEdit.sessionId = null;
  draft.ui.latestTurnEdit.messageIndex = -1;
  draft.ui.latestTurnEdit.originalContent = "";
  draft.ui.latestTurnEdit.draft = "";
}

function shouldClearLatestTurnEditForSession(draft, sessionId) {
  if (!draft.ui.latestTurnEdit.active) {
    return false;
  }
  if (!sessionId) {
    return true;
  }
  return draft.ui.latestTurnEdit.sessionId !== sessionId;
}

function persist() {
  persistStateSnapshot({
    currentProjectId: state.currentProjectId,
    currentSessionId: state.currentSessionId,
    sidebar: buildPersistedSidebarState(),
  });
}

function notify() {
  for (const listener of listeners) {
    listener(state);
  }
}

function commit(mutator, shouldPersist = true) {
  mutator(state);
  if (shouldPersist) {
    persist();
  }
  notify();
}

export function subscribe(listener) {
  listeners.add(listener);
  listener(state);
  return () => listeners.delete(listener);
}

export function getState() {
  return state;
}

export function getMessagesForCurrentSession() {
  return getMessagesForSession(state.currentSessionId || DRAFT_SESSION_KEY);
}

export function getMessagesForSession(sessionId) {
  const key = sessionId || DRAFT_SESSION_KEY;
  return Array.isArray(state.messageMap[key]) ? state.messageMap[key] : [];
}

export function getMemoryForSession(sessionId) {
  if (!sessionId) {
    return null;
  }
  return state.memoryMap[sessionId] || null;
}

export function getStableFactsForProject(projectId) {
  if (!projectId) {
    return [];
  }
  return Array.isArray(state.stableFactMap[projectId]) ? state.stableFactMap[projectId] : [];
}

export function getDebugForSession(sessionId) {
  if (!sessionId) {
    return null;
  }
  return state.chatDebugMap[sessionId] || null;
}

export function setBackendBaseUrl(backendBaseUrl) {
  commit((draft) => {
    draft.backendBaseUrl = backendBaseUrl;
  });
}

export function setCurrentProjectId(projectId) {
  commit((draft) => {
    draft.currentProjectId = projectId;
  });
}

export function setCurrentSessionId(sessionId) {
  commit((draft) => {
    draft.currentSessionId = sessionId;
    if (shouldClearLatestTurnEditForSession(draft, sessionId)) {
      resetLatestTurnEditState(draft);
    }
  });
}

export function clearCurrentSessionSelection() {
  commit((draft) => {
    draft.currentSessionId = null;
    draft.selectedSessionDetail = null;
    resetLatestTurnEditState(draft);
  });
}

export function setProjects(projects) {
  commit(
    (draft) => {
      draft.projects = Array.isArray(projects) ? projects : [];
    },
    false,
  );
}

export function setSessions(sessions) {
  commit(
    (draft) => {
      draft.sessions = Array.isArray(sessions) ? sessions : [];
      if (draft.currentSessionId) {
        const match = draft.sessions.find((item) => item.id === draft.currentSessionId);
        if (match) {
          draft.selectedSessionDetail = match;
        }
      }
    },
    false,
  );
}

export function setSelectedProjectDetail(project) {
  commit(
    (draft) => {
      draft.selectedProjectDetail = project;
    },
    false,
  );
}

export function setSelectedSessionDetail(session) {
  commit(
    (draft) => {
      draft.selectedSessionDetail = session;
      if (!session || session.status === "archived") {
        resetLatestTurnEditState(draft);
      }
    },
    false,
  );
}

export function setHealth(healthPatch) {
  commit(
    (draft) => {
      draft.health = {
        ...draft.health,
        ...healthPatch,
      };
    },
    false,
  );
}

export function setBusy(scope, value) {
  commit(
    (draft) => {
      draft.busy[scope] = value;
    },
    false,
  );
}

export function setNotice(scope, message, variant = "info") {
  commit(
    (draft) => {
      draft.notices[scope] = message ? { message, variant } : null;
    },
    false,
  );
}

export function clearNotice(scope) {
  setNotice(scope, null);
}

export function setMemoryForSession(sessionId, memory) {
  if (!sessionId) {
    return;
  }

  commit((draft) => {
    const nextMemory = memory
      ? {
          working_memory: memory.working_memory || null,
          session_digest: memory.session_digest || null,
        }
      : null;

    if (nextMemory && (nextMemory.working_memory || nextMemory.session_digest)) {
      draft.memoryMap[sessionId] = nextMemory;
    } else {
      delete draft.memoryMap[sessionId];
    }
  });
}

export function setStableFactsForProject(projectId, facts) {
  if (!projectId) {
    return;
  }

  commit(
    (draft) => {
      draft.stableFactMap[projectId] = Array.isArray(facts) ? facts : [];
    },
    false,
  );
}

export function clearStableFactsForProject(projectId) {
  if (!projectId) {
    return;
  }

  commit(
    (draft) => {
      delete draft.stableFactMap[projectId];
    },
    false,
  );
}

export function setMessagesForSession(sessionId, messages) {
  if (!sessionId) {
    return;
  }

  commit((draft) => {
    draft.messageMap[sessionId] = Array.isArray(messages) ? messages : [];
  });
}

export function appendMessage(sessionId, message) {
  const key = sessionId || DRAFT_SESSION_KEY;
  commit((draft) => {
    if (!Array.isArray(draft.messageMap[key])) {
      draft.messageMap[key] = [];
    }
    draft.messageMap[key].push(message);
  });
}

export function removeMessage(sessionId, targetMessage) {
  const key = sessionId || DRAFT_SESSION_KEY;
  commit((draft) => {
    const current = Array.isArray(draft.messageMap[key]) ? draft.messageMap[key] : [];
    draft.messageMap[key] = current.filter((message) => message !== targetMessage);
  });
}

export function removeSessionData(sessionId) {
  if (!sessionId) {
    return;
  }

  commit((draft) => {
    delete draft.messageMap[sessionId];
    delete draft.memoryMap[sessionId];
    delete draft.chatDebugMap[sessionId];
    if (draft.ui.latestTurnEdit.sessionId === sessionId) {
      resetLatestTurnEditState(draft);
    }
  });
}

export function setChatDebug(sessionId, debug) {
  if (!sessionId) {
    return;
  }

  commit(
    (draft) => {
      draft.chatDebugMap[sessionId] = debug;
    },
    false,
  );
}

export function toggleSidebarSection(sectionKey) {
  commit((draft) => {
    draft.ui.sidebar.collapsedSections[sectionKey] =
      !draft.ui.sidebar.collapsedSections[sectionKey];
  });
}

export function toggleShowAllProjects() {
  commit((draft) => {
    draft.ui.sidebar.showAllProjects = !draft.ui.sidebar.showAllProjects;
  });
}

export function toggleShowAllUnassigned() {
  commit((draft) => {
    draft.ui.sidebar.showAllUnassigned = !draft.ui.sidebar.showAllUnassigned;
  });
}

export function toggleProjectExpanded(projectId) {
  const key = String(projectId);
  commit((draft) => {
    draft.ui.sidebar.expandedProjectIds[key] = !draft.ui.sidebar.expandedProjectIds[key];
  });
}

export function setProjectExpanded(projectId, isExpanded) {
  const key = String(projectId);
  commit((draft) => {
    draft.ui.sidebar.expandedProjectIds[key] = Boolean(isExpanded);
  });
}

export function toggleProjectSessionExpansion(projectId) {
  const key = String(projectId);
  commit((draft) => {
    draft.ui.sidebar.expandedProjectSessionIds[key] =
      !draft.ui.sidebar.expandedProjectSessionIds[key];
  });
}

export function setProjectModalState({ isOpen, mode, projectId, stableFactId }) {
  commit(
    (draft) => {
      if (typeof isOpen === "boolean") {
        draft.ui.projectModalOpen = isOpen;
      }
      if (mode) {
        draft.ui.projectModalMode = mode;
      }
      if (projectId !== undefined) {
        draft.ui.editingProjectId = projectId;
      }
      if (stableFactId !== undefined) {
        draft.ui.editingStableFactId = stableFactId;
      }
    },
    false,
  );
}

export function setProjectModalOpen(isOpen) {
  setProjectModalState({
    isOpen: Boolean(isOpen),
    mode: isOpen ? state.ui.projectModalMode : "create",
    projectId: isOpen ? state.ui.editingProjectId : null,
    stableFactId: isOpen ? state.ui.editingStableFactId : null,
  });
}

export function setEditingStableFactId(stableFactId) {
  setProjectModalState({ stableFactId });
}

export function setNewChatMenuOpen(isOpen) {
  const nextValue = Boolean(isOpen);
  if (state.ui.newChatMenuOpen === nextValue) {
    return;
  }

  commit(
    (draft) => {
      draft.ui.newChatMenuOpen = nextValue;
    },
    false,
  );
}


export function setLatestTurnEditMode(sessionId, messageIndex, originalContent = "") {
  if (!sessionId || Number.isNaN(Number(messageIndex))) {
    return;
  }

  commit(
    (draft) => {
      draft.ui.latestTurnEdit.active = true;
      draft.ui.latestTurnEdit.sessionId = sessionId;
      draft.ui.latestTurnEdit.messageIndex = Number(messageIndex);
      draft.ui.latestTurnEdit.originalContent = originalContent || "";
      draft.ui.latestTurnEdit.draft = originalContent || "";
    },
    false,
  );
}

export function updateLatestTurnEditDraft(draftValue) {
  commit(
    (draft) => {
      if (!draft.ui.latestTurnEdit.active) {
        return;
      }
      draft.ui.latestTurnEdit.draft = draftValue ?? "";
    },
    false,
  );
}

export function clearLatestTurnEditMode() {
  commit(
    (draft) => {
      resetLatestTurnEditState(draft);
    },
    false,
  );
}
