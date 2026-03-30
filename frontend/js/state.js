import {
  DEFAULT_BACKEND_BASE_URL,
  loadPersistedState,
  persistStateSnapshot,
} from "./storage.js";

export const DRAFT_SESSION_KEY = "__draft__";

const persisted = loadPersistedState();
const listeners = new Set();

const state = {
  backendBaseUrl: persisted.backendBaseUrl || DEFAULT_BACKEND_BASE_URL,
  currentProjectId: persisted.currentProjectId,
  currentSessionId: persisted.currentSessionId,
  summaryMap: persisted.summaryMap || {},
  messageMap: persisted.messageMap || {},
  chatDebugMap: {},
  projects: [],
  sessions: [],
  selectedProjectDetail: null,
  selectedSessionDetail: null,
  filterSessionsByProject: true,
  health: {
    status: "idle",
    label: "未检测",
    environment: "未知",
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
};

function persist() {
  persistStateSnapshot({
    backendBaseUrl: state.backendBaseUrl,
    currentProjectId: state.currentProjectId,
    currentSessionId: state.currentSessionId,
    summaryMap: state.summaryMap,
    messageMap: state.messageMap,
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

export function getActiveSessionKey() {
  return state.currentSessionId || DRAFT_SESSION_KEY;
}

export function getMessagesForCurrentSession() {
  return getMessagesForSession(state.currentSessionId || DRAFT_SESSION_KEY);
}

export function getMessagesForSession(sessionId) {
  const key = sessionId || DRAFT_SESSION_KEY;
  return Array.isArray(state.messageMap[key]) ? state.messageMap[key] : [];
}

export function getSummaryForSession(sessionId) {
  if (!sessionId) {
    return null;
  }
  return state.summaryMap[sessionId] || null;
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
  });
}

export function clearCurrentSessionSelection() {
  commit((draft) => {
    draft.currentSessionId = null;
    draft.selectedSessionDetail = null;
  });
}

export function setProjects(projects) {
  commit((draft) => {
    draft.projects = Array.isArray(projects) ? projects : [];
  }, false);
}

export function setSessions(sessions) {
  commit((draft) => {
    draft.sessions = Array.isArray(sessions) ? sessions : [];
    if (draft.currentSessionId) {
      const match = draft.sessions.find((item) => item.id === draft.currentSessionId);
      if (match) {
        draft.selectedSessionDetail = match;
      }
    }
  }, false);
}

export function setSelectedProjectDetail(project) {
  commit((draft) => {
    draft.selectedProjectDetail = project;
  }, false);
}

export function setSelectedSessionDetail(session) {
  commit((draft) => {
    draft.selectedSessionDetail = session;
  }, false);
}

export function setHealth(healthPatch) {
  commit((draft) => {
    draft.health = {
      ...draft.health,
      ...healthPatch,
    };
  }, false);
}

export function setBusy(scope, value) {
  commit((draft) => {
    draft.busy[scope] = value;
  }, false);
}

export function setNotice(scope, message, variant = "info") {
  commit((draft) => {
    draft.notices[scope] = message ? { message, variant } : null;
  }, false);
}

export function clearNotice(scope) {
  setNotice(scope, null);
}

export function setFilterSessionsByProject(enabled) {
  commit((draft) => {
    draft.filterSessionsByProject = Boolean(enabled);
  }, false);
}

export function setSummaryForSession(sessionId, summary) {
  if (!sessionId) {
    return;
  }

  commit((draft) => {
    if (summary) {
      draft.summaryMap[sessionId] = summary;
    } else {
      delete draft.summaryMap[sessionId];
    }
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

export function moveDraftToSession(sessionId) {
  if (!sessionId) {
    return;
  }

  commit((draft) => {
    const draftMessages = Array.isArray(draft.messageMap[DRAFT_SESSION_KEY])
      ? draft.messageMap[DRAFT_SESSION_KEY]
      : [];

    if (!Array.isArray(draft.messageMap[sessionId])) {
      draft.messageMap[sessionId] = [];
    }

    if (draftMessages.length > 0) {
      draft.messageMap[sessionId] = [...draft.messageMap[sessionId], ...draftMessages];
    }

    delete draft.messageMap[DRAFT_SESSION_KEY];
  });
}

export function clearDraftMessages() {
  commit((draft) => {
    delete draft.messageMap[DRAFT_SESSION_KEY];
  });
}

export function setChatDebug(sessionId, debug) {
  if (!sessionId) {
    return;
  }

  commit((draft) => {
    draft.chatDebugMap[sessionId] = debug;
  }, false);
}
