import {
  getAccessModeHelpText,
  getAccessModeLabel,
  getPrivacyHelpText,
  getPrivacyLabel,
  getProjectBindingLabel,
  getSessionTitle,
  getStatusLabel,
} from "./labels.js";

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function badge(text, variant = "soft") {
  return `<span class="badge ${variant}">${escapeHtml(text)}</span>`;
}

function renderNotice(element, notice) {
  if (!element) {
    return;
  }

  if (!notice?.message) {
    element.className = "notice hidden";
    element.textContent = "";
    return;
  }

  element.className = `notice ${notice.variant || "info"}`;
  element.textContent = notice.message;
}

function renderProjectDetail(state, elements) {
  const project = state.selectedProjectDetail;
  elements.currentProjectLabel.textContent = project ? `${project.name} (#${project.id})` : "未选中";

  if (!project) {
    elements.projectDetail.className = "detail-card empty-card";
    elements.projectDetail.innerHTML = "未选中项目，可先创建或从列表中选择。";
    return;
  }

  const description = project.description
    ? `<p class="detail-copy">${escapeHtml(project.description)}</p>`
    : '<p class="detail-copy muted">没有描述。</p>';

  elements.projectDetail.className = "detail-card";
  elements.projectDetail.innerHTML = `
    <div class="detail-head">
      <strong>${escapeHtml(project.name)}</strong>
      <div class="tag-row">
        ${badge(getAccessModeLabel(project.access_mode), "scope")}
        ${badge(getStatusLabel(project.status), project.status === "active" ? "success" : "warning")}
      </div>
    </div>
    ${description}
    <p class="detail-copy">${escapeHtml(getAccessModeHelpText(project.access_mode))}</p>
    <div class="detail-meta">
      <span>项目 ID: ${project.id}</span>
      <span>创建时间: ${escapeHtml(project.created_at || "-")}</span>
    </div>
  `;
}

function renderProjectList(state, elements) {
  if (!state.projects.length) {
    elements.projectList.innerHTML = '<div class="empty-card">当前没有项目。先创建一个项目，再测试开放项目和仅限项目的访问边界。</div>';
    return;
  }

  elements.projectList.innerHTML = state.projects
    .map((project) => {
      const selected = state.currentProjectId === project.id ? "selected" : "";
      return `
        <article class="entity-card ${selected}">
          <button class="entity-main" type="button" data-project-select="${project.id}">
            <div class="entity-title-row">
              <strong>${escapeHtml(project.name)}</strong>
              <span class="entity-id">#${project.id}</span>
            </div>
            <div class="tag-row">
              ${badge(getAccessModeLabel(project.access_mode), "scope")}
              ${badge(getStatusLabel(project.status), project.status === "active" ? "success" : "warning")}
            </div>
          </button>
        </article>
      `;
    })
    .join("");
}

function renderSessionDetail(state, elements) {
  const session = state.selectedSessionDetail;
  elements.currentSessionLabel.textContent = session ? `${session.id.slice(0, 12)}...` : "未选中";

  if (!session) {
    elements.sessionDetail.className = "detail-card empty-card";
    elements.sessionDetail.innerHTML = "未选中会话。请先创建空白会话，或从列表中选择已有会话后再聊天。";
    elements.sessionBanner.className = "notice info";
    elements.sessionBanner.textContent = "当前未选中会话。右侧聊天区会禁止发送消息，直到你显式选择或创建一个会话。";
    return;
  }

  const project = state.projects.find((item) => item.id === session.project_id);
  const projectLabel = project ? `${project.name} (#${project.id})` : "无项目会话";

  elements.sessionDetail.className = "detail-card";
  elements.sessionDetail.innerHTML = `
    <div class="detail-head">
      <strong>${escapeHtml(getSessionTitle(session.title))}</strong>
      <div class="tag-row">
        ${badge(getPrivacyLabel(session.is_private), session.is_private ? "danger" : "soft")}
        ${badge(getStatusLabel(session.status), session.status === "active" ? "success" : session.status === "archived" ? "warning" : "danger")}
        ${badge(getProjectBindingLabel(session.project_id), "soft")}
      </div>
    </div>
    <p class="detail-copy">${escapeHtml(getPrivacyHelpText(session.is_private))}</p>
    <div class="detail-meta stacked">
      <span>会话 ID: ${escapeHtml(session.id)}</span>
      <span>项目归属: ${escapeHtml(projectLabel)}</span>
      <span>当前可见性: ${escapeHtml(getPrivacyLabel(session.is_private))}</span>
      <span>更新时间: ${escapeHtml(session.updated_at || "-")}</span>
    </div>
  `;

  if (session.status === "deleted") {
    elements.sessionBanner.className = "notice danger";
    elements.sessionBanner.textContent = "当前会话已被软删除。页面会保留状态展示，但禁止继续向这个会话发消息。";
    return;
  }

  if (session.status === "archived") {
    elements.sessionBanner.className = "notice warning";
    elements.sessionBanner.textContent = "当前会话已归档。页面会保留状态展示，但禁止继续向这个会话发消息。";
    return;
  }

  elements.sessionBanner.className = "notice hidden";
  elements.sessionBanner.textContent = "";
}

function renderSessionList(state, elements) {
  if (!state.sessions.length) {
    elements.sessionList.innerHTML = '<div class="empty-card">当前筛选下没有会话。你可以创建一个空白会话，或切换成“全部”查看。</div>';
    return;
  }

  elements.sessionList.innerHTML = state.sessions
    .map((session) => {
      const selected = state.currentSessionId === session.id ? "selected" : "";
      return `
        <article class="entity-card ${selected}">
          <button class="entity-main" type="button" data-session-select="${escapeHtml(session.id)}">
            <div class="entity-title-row">
              <strong>${escapeHtml(getSessionTitle(session.title))}</strong>
              <span class="entity-id">${escapeHtml(session.id.slice(0, 10))}</span>
            </div>
            <div class="tag-row">
              ${badge(session.project_id ? `归属项目 #${session.project_id}` : "无项目会话", "soft")}
              ${badge(getPrivacyLabel(session.is_private), session.is_private ? "danger" : "soft")}
              ${badge(getStatusLabel(session.status), session.status === "active" ? "success" : session.status === "archived" ? "warning" : "danger")}
            </div>
          </button>
          <div class="entity-actions">
            <button class="mini-button" type="button" data-session-archive="${escapeHtml(session.id)}">归档</button>
            <button class="mini-button danger" type="button" data-session-delete="${escapeHtml(session.id)}">删除</button>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderProjectSelectOptions(state, elements) {
  const sessionOptions = [
    '<option value="">无项目会话</option>',
    ...state.projects.map(
      (project) => `<option value="${project.id}">${escapeHtml(project.name)} (#${project.id})</option>`,
    ),
  ];

  const preferredValue = state.currentProjectId ? String(state.currentProjectId) : "";
  elements.sessionProjectSelect.innerHTML = sessionOptions.join("");
  elements.sessionProjectSelect.value = preferredValue;

  const moveOptions = [
    '<option value="">选择目标项目</option>',
    '<option value="__none__">移出当前项目，变成无项目会话</option>',
    ...state.projects.map(
      (project) => `<option value="${project.id}">${escapeHtml(project.name)} (#${project.id})</option>`,
    ),
  ];
  elements.moveProjectSelect.innerHTML = moveOptions.join("");
}

export function renderManagement(state, elements) {
  renderNotice(elements.globalNotice, state.notices.global);
  renderNotice(elements.projectNotice, state.notices.projects);
  renderNotice(elements.sessionNotice, state.notices.sessions);

  elements.healthBadge.className = `badge ${state.health.status || "neutral"}`;
  elements.healthBadge.textContent = state.health.label;
  elements.environmentValue.textContent = state.health.environment || "未知";
  elements.backendBaseUrl.value = state.backendBaseUrl;
  elements.filterSessionsByProject.checked = state.filterSessionsByProject;

  renderProjectDetail(state, elements);
  renderProjectList(state, elements);
  renderSessionDetail(state, elements);
  renderSessionList(state, elements);
  renderProjectSelectOptions(state, elements);

  const hasSelectedSession = Boolean(state.selectedSessionDetail);
  const selectedSessionLocked = ["archived", "deleted"].includes(
    state.selectedSessionDetail?.status,
  );

  elements.archiveSessionButton.disabled = !hasSelectedSession || selectedSessionLocked;
  elements.deleteSessionButton.disabled = !hasSelectedSession || state.selectedSessionDetail?.status === "deleted";
  elements.moveSessionButton.disabled = !hasSelectedSession || selectedSessionLocked;
}
