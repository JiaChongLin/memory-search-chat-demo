import { healthCheck, listProjects, listSessions, normalizeBaseUrl } from "./api.js";
import {
  clearNotice,
  getState,
  setBackendBaseUrl,
  setBusy,
  setCurrentProjectId,
  setHealth,
  setProjects,
  setSelectedProjectDetail,
  setSessions,
  setNotice,
} from "./state.js";
import { formatErrorMessage } from "./helpers/ui-helpers.js";

export function createAppRuntime({
  syncSelectedSessionDetail,
  ensureSessionMessages,
  ensureSessionSummary,
}) {
  function getBaseUrl() {
    return normalizeBaseUrl(getState().backendBaseUrl);
  }

  function canChatWithCurrentSelection() {
    const state = getState();
    const session = state.selectedSessionDetail;
    if (!session) {
      return false;
    }
    return session.status !== "archived";
  }

  async function refreshHealth(silent = false) {
    setBusy("health", true);
    try {
      const baseUrl = getBaseUrl();
      await healthCheck(baseUrl);
      setBackendBaseUrl(baseUrl);
      setHealth({ status: "success", label: "连接正常", environment: "connected" });
      if (!silent) {
        clearNotice("global");
      }
    } catch (error) {
      setHealth({ status: "warning", label: "后端不可用", environment: "unavailable" });
      if (!silent) {
        setNotice("global", `后端连接失败：${formatErrorMessage(error)}`, "danger");
      }
    } finally {
      setBusy("health", false);
    }
  }

  async function refreshProjects(options = {}) {
    setBusy("projects", true);
    try {
      const projects = await listProjects(getBaseUrl());
      setProjects(projects);

      const state = getState();
      if (state.currentProjectId !== null) {
        const selected = projects.find((item) => item.id === state.currentProjectId) || null;
        setSelectedProjectDetail(selected);
        if (!selected) {
          setCurrentProjectId(null);
        }
      }

      if (!options.silent) {
        clearNotice("projects");
      }
    } catch (error) {
      setNotice("projects", `加载项目失败：${formatErrorMessage(error)}`, "danger");
    } finally {
      setBusy("projects", false);
    }
  }

  async function refreshSessions(options = {}) {
    setBusy("sessions", true);
    try {
      const sessions = await listSessions(getBaseUrl());
      setSessions(sessions);
      await syncSelectedSessionDetail();

      const state = getState();
      if (state.currentSessionId) {
        await ensureSessionSummary(state.currentSessionId, {
          force: Boolean(options.forceSummary),
        });

        if (options.loadMessages !== false) {
          await ensureSessionMessages(state.currentSessionId, {
            force: Boolean(options.forceMessages),
          });
        }
      }

      if (!options.silent) {
        clearNotice("sessions");
      }
    } catch (error) {
      setNotice("sessions", `加载会话失败：${formatErrorMessage(error)}`, "danger");
    } finally {
      setBusy("sessions", false);
    }
  }

  return {
    getBaseUrl,
    getState,
    canChatWithCurrentSelection,
    refreshHealth,
    refreshProjects,
    refreshSessions,
  };
}
