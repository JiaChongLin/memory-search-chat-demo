export const STORAGE_KEYS = {
  currentProjectId: "memory-search-chat-demo.currentProjectId",
  currentSessionId: "memory-search-chat-demo.currentSessionId",
  sidebar: "memory-search-chat-demo.sidebar",
};

export const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8000";

const DEFAULT_SIDEBAR_STATE = {
  collapsedSections: {
    projects: false,
    unassigned: false,
  },
  showAllProjects: false,
  showAllUnassigned: false,
  expandedProjectIds: [],
  expandedProjectSessionIds: [],
};

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
    showAllUnassigned: Boolean(rawValue.showAllUnassigned),
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
    currentProjectId: parseOptionalInt(
      localStorage.getItem(STORAGE_KEYS.currentProjectId),
    ),
    currentSessionId: localStorage.getItem(STORAGE_KEYS.currentSessionId),
    sidebar: normalizeSidebarState(loadSidebarState()),
  };
}

function loadSidebarState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.sidebar);
    if (!raw) {
      return DEFAULT_SIDEBAR_STATE;
    }
    return JSON.parse(raw) ?? DEFAULT_SIDEBAR_STATE;
  } catch {
    return DEFAULT_SIDEBAR_STATE;
  }
}

export function persistStateSnapshot(snapshot) {
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
    STORAGE_KEYS.sidebar,
    JSON.stringify(snapshot.sidebar || DEFAULT_SIDEBAR_STATE),
  );

  // Drop legacy heavy payloads so refresh recovery depends on session re-fetching instead.
  localStorage.removeItem("memory-search-chat-demo.backendBaseUrl");
  localStorage.removeItem("memory-search-chat-demo.summary");
  localStorage.removeItem("memory-search-chat-demo.messages");
}
