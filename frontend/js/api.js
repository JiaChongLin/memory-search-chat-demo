function buildUrl(baseUrl, path, query) {
  const url = new URL(path, `${baseUrl.replace(/\/+$/, "")}/`);

  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") {
        return;
      }
      url.searchParams.set(key, String(value));
    });
  }

  return url.toString();
}

async function requestJson(baseUrl, path, options = {}, query) {
  const response = await fetch(buildUrl(baseUrl, path, query), {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const error = new Error(payload?.error?.message || `HTTP ${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  return payload;
}

export function normalizeBaseUrl(value) {
  const normalized = (value || "").trim().replace(/\/+$/, "");
  return normalized || "http://127.0.0.1:8000";
}

export function healthCheck(baseUrl) {
  return requestJson(baseUrl, "/health", { method: "GET" });
}

export function listProjects(baseUrl) {
  return requestJson(baseUrl, "/api/projects", { method: "GET" });
}

export function getProject(baseUrl, projectId) {
  return requestJson(baseUrl, `/api/projects/${projectId}`, { method: "GET" });
}

export function createProject(baseUrl, payload) {
  return requestJson(baseUrl, "/api/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteProject(baseUrl, projectId) {
  return requestJson(baseUrl, `/api/projects/${projectId}`, {
    method: "DELETE",
  });
}

export function listSessions(baseUrl, query = {}) {
  return requestJson(baseUrl, "/api/sessions", { method: "GET" }, {
    include_archived: true,
    ...query,
  });
}

export function getSession(baseUrl, sessionId) {
  return requestJson(baseUrl, `/api/sessions/${sessionId}`, { method: "GET" });
}

export function createSession(baseUrl, payload) {
  return requestJson(baseUrl, "/api/sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function archiveSession(baseUrl, sessionId) {
  return requestJson(baseUrl, `/api/sessions/${sessionId}/archive`, {
    method: "POST",
  });
}

export function deleteSession(baseUrl, sessionId) {
  return requestJson(baseUrl, `/api/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

export function moveSession(baseUrl, sessionId, projectId) {
  return requestJson(baseUrl, `/api/sessions/${sessionId}/move`, {
    method: "POST",
    body: JSON.stringify({ project_id: projectId }),
  });
}

export function sendChat(baseUrl, payload) {
  return requestJson(baseUrl, "/api/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
