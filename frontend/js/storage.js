export const STORAGE_KEYS = {
  backendBaseUrl: "memory-search-chat-demo.backendBaseUrl",
  currentProjectId: "memory-search-chat-demo.currentProjectId",
  currentSessionId: "memory-search-chat-demo.currentSessionId",
  summary: "memory-search-chat-demo.summary",
  messages: "memory-search-chat-demo.messages",
  sidebar: "memory-search-chat-demo.sidebar",
};

export const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8000";

const DEFAULT_SIDEBAR_STATE = {
  collapsedSections: {
    projects: false,
    unassigned: false,
  },
  showAllProjects: false,
  expandedProjectIds: [],
  expandedProjectSessionIds: [],
};

function readJson(key, fallbackValue) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) {
      return fallbackValue;
    }
    const parsed = JSON.parse(raw);
    return parsed ?? fallbackValue;
  } catch {
    return fallbackValue;
  }
}

function parseOptionalInt(rawValue) {
  if (rawValue === null || rawValue === "") {
    return null;
  }

  const parsed = Number.parseInt(rawValue, 10);
  return Number.isNaN(parsed) ? null : parsed;
}

function normalizeSidebarState(rawValue) {
  if (!rawValue || typeof rawValue !== "object") {
    return DEFAULT_SIDEBAR_STATE;
  }

  return {
    collapsedSections: {
      projects: Boolean(rawValue.collapsedSections?.projects),
      unassigned: Boolean(rawValue.collapsedSections?.unassigned),
    },
    showAllProjects: Boolean(rawValue.showAllProjects),
    expandedProjectIds: Array.isArray(rawValue.expandedProjectIds)
      ? rawValue.expandedProjectIds
      : [],
    expandedProjectSessionIds: Array.isArray(rawValue.expandedProjectSessionIds)
      ? rawValue.expandedProjectSessionIds
      : [],
  };
}

export function loadPersistedState() {
  return {
    backendBaseUrl:
      localStorage.getItem(STORAGE_KEYS.backendBaseUrl) || DEFAULT_BACKEND_BASE_URL,
    currentProjectId: parseOptionalInt(
      localStorage.getItem(STORAGE_KEYS.currentProjectId),
    ),
    currentSessionId: localStorage.getItem(STORAGE_KEYS.currentSessionId),
    summaryMap: readJson(STORAGE_KEYS.summary, {}),
    messageMap: readJson(STORAGE_KEYS.messages, {}),
    sidebar: normalizeSidebarState(readJson(STORAGE_KEYS.sidebar, DEFAULT_SIDEBAR_STATE)),
  };
}

export function persistStateSnapshot(snapshot) {
  if (snapshot.backendBaseUrl) {
    localStorage.setItem(STORAGE_KEYS.backendBaseUrl, snapshot.backendBaseUrl);
  } else {
    localStorage.removeItem(STORAGE_KEYS.backendBaseUrl);
  }

  if (snapshot.currentProjectId === null || snapshot.currentProjectId === undefined) {
    localStorage.removeItem(STORAGE_KEYS.currentProjectId);
  } else {
    localStorage.setItem(
      STORAGE_KEYS.currentProjectId,
      String(snapshot.currentProjectId),
    );
  }

  if (snapshot.currentSessionId) {
    localStorage.setItem(STORAGE_KEYS.currentSessionId, snapshot.currentSessionId);
  } else {
    localStorage.removeItem(STORAGE_KEYS.currentSessionId);
  }

  localStorage.setItem(
    STORAGE_KEYS.summary,
    JSON.stringify(snapshot.summaryMap || {}),
  );
  localStorage.setItem(
    STORAGE_KEYS.messages,
    JSON.stringify(snapshot.messageMap || {}),
  );
  localStorage.setItem(
    STORAGE_KEYS.sidebar,
    JSON.stringify(snapshot.sidebar || DEFAULT_SIDEBAR_STATE),
  );
}
