import {
  getAccessModeHelpText,
  getAccessModeLabel,
  getPrivacyHelpText,
  getPrivacyLabel,
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

function getProjectSessions(state, projectId) {
  return state.sessions.filter((session) => session.project_id === projectId);
}

function getUnassignedSessions(state) {
  return state.sessions.filter((session) => session.project_id === null);
}

function renderSessionButton(state, session) {
  const selected = state.currentSessionId === session.id ? "selected" : "";
  return `
    <button
      class="nav-session-item ${selected}"
      type="button"
      data-session-select="${escapeHtml(session.id)}"
    >
      <span class="nav-session-title">${escapeHtml(getSessionTitle(session.title))}</span>
      <span class="nav-session-tags">
        ${session.is_private ? badge("私密", "danger") : ""}
        ${session.status === "archived" ? badge("归档", "warning") : ""}
      </span>
    </button>
  `;
}

function renderSidebarProjectItem(state, project) {
  const sessions = getProjectSessions(state, project.id);
  const isSelected = state.currentProjectId === project.id;
  const isExpanded = Boolean(state.ui.sidebar.expandedProjectIds[String(project.id)]);
  const showAllSessions = Boolean(
    state.ui.sidebar.expandedProjectSessionIds[String(project.id)],
  );
  const visibleSessions = showAllSessions ? sessions : sessions.slice(0, 5);
  const hasMoreSessions = sessions.length > 5;

  return `
    <article class="nav-project-card ${isSelected ? "selected" : ""}">
      <div class="nav-project-top">
        <button class="nav-project-main" type="button" data-project-select="${project.id}">
          <span class="nav-project-title-row">
            <strong>${escapeHtml(project.name)}</strong>
            <span class="nav-count">${sessions.length}</span>
          </span>
          <span class="nav-project-meta">
            ${badge(getAccessModeLabel(project.access_mode), "scope")}
          </span>
        </button>
        <button
          class="nav-toggle-button"
          type="button"
          data-project-toggle="${project.id}"
          aria-expanded="${isExpanded}"
          title="${isExpanded ? "收起项目" : "展开项目"}"
        >
          ${isExpanded ? "－" : "＋"}
        </button>
      </div>
      ${
        isExpanded
          ? `
            <div class="nav-project-children">
              ${
                sessions.length
                  ? `
                    <div class="nav-session-list">
                      ${visibleSessions.map((session) => renderSessionButton(state, session)).join("")}
                    </div>
                    ${
                      hasMoreSessions
                        ? `<button class="nav-more-button" type="button" data-project-sessions-toggle="${project.id}">${showAllSessions ? "收起会话" : "更多会话"}</button>`
                        : ""
                    }
                  `
                  : '<div class="nav-empty">当前项目下还没有会话，可以先新建聊天。</div>'
              }
              ${
                isSelected
                  ? `<button class="nav-more-button" type="button" data-project-delete="${project.id}">删除当前项目</button>`
                  : ""
              }
            </div>
          `
          : ""
      }
    </article>
  `;
}

function renderProjectsSection(state, elements) {
  const collapsed = state.ui.sidebar.collapsedSections.projects;
  const showAllProjects = state.ui.sidebar.showAllProjects;
  const projects = showAllProjects ? state.projects : state.projects.slice(0, 5);
  const hasMoreProjects = state.projects.length > 5;

  elements.projectsSection.innerHTML = `
    <div class="sidebar-section-head">
      <button class="sidebar-section-toggle" type="button" data-section-toggle="projects">
        <span>项目</span>
        <span class="sidebar-toggle-icon">${collapsed ? "＋" : "－"}</span>
      </button>
      <button id="openProjectModalButton" class="icon-button" type="button" title="新建项目">＋</button>
    </div>
    ${
      collapsed
        ? ""
        : `
          <div class="sidebar-section-body">
            <div class="sidebar-note">项目访问模式决定跨项目边界。项目删除后，会级联删除项目内所有会话、消息和摘要。</div>
            <div class="nav-list">
              ${
                projects.length
                  ? projects.map((project) => renderSidebarProjectItem(state, project)).join("")
                  : '<div class="nav-empty">还没有项目。可以先创建一个开放项目或仅限项目。</div>'
              }
            </div>
            ${
              hasMoreProjects
                ? `<button class="nav-more-button" type="button" data-projects-more-toggle="true">${showAllProjects ? "收起项目" : "更多项目"}</button>`
                : ""
            }
          </div>
        `
    }
  `;
}

function renderUnassignedSection(state, elements) {
  const collapsed = state.ui.sidebar.collapsedSections.unassigned;
  const sessions = getUnassignedSessions(state);
  const showAllUnassigned = state.ui.sidebar.showAllUnassigned;
  const visibleSessions = showAllUnassigned ? sessions : sessions.slice(0, 10);
  const hasMoreSessions = sessions.length > 10;

  elements.unassignedSection.innerHTML = `
    <div class="sidebar-section-head">
      <button class="sidebar-section-toggle" type="button" data-section-toggle="unassigned">
        <span>未归属会话</span>
        <span class="sidebar-toggle-icon">${collapsed ? "＋" : "－"}</span>
      </button>
    </div>
    ${
      collapsed
        ? ""
        : `
          <div class="sidebar-section-body">
            <div class="sidebar-note">这里只展示没有挂到任何项目的会话。</div>
            <div class="unassigned-list">
              ${
                visibleSessions.length
                  ? visibleSessions.map((session) => renderSessionButton(state, session)).join("")
                  : '<div class="nav-empty">当前还没有未归属会话。</div>'
              }
            </div>
            ${
              hasMoreSessions
                ? `<button class="nav-more-button" type="button" data-unassigned-more-toggle="true">${showAllUnassigned ? "收起会话" : "更多会话"}</button>`
                : ""
            }
          </div>
        `
    }
  `;
}

function renderCurrentSessionPanel(state, elements) {
  const session = state.selectedSessionDetail;
  const project = state.projects.find((item) => item.id === session?.project_id) || null;

  if (!session) {
    elements.sessionDetail.innerHTML = `
      <div class="session-side-card">
        <div class="mini-head">
          <h3>会话操作</h3>
          <span class="badge neutral">未选择</span>
        </div>
        <p class="detail-copy">选择会话后，这里会显示移动、归档和删除等操作。</p>
      </div>
    `;
    elements.sessionBanner.className = "notice hidden";
    elements.sessionBanner.textContent = "";
    return;
  }

  elements.sessionDetail.innerHTML = `
    <div class="session-side-card">
      <div class="mini-head">
        <h3>会话操作</h3>
        <span class="badge ${session.status === "active" ? "success" : "warning"}">${escapeHtml(
          getStatusLabel(session.status),
        )}</span>
      </div>
      <p class="detail-copy">${escapeHtml(getPrivacyHelpText(session.is_private))}</p>
      <div class="detail-meta stacked">
        <span>会话 ID：${escapeHtml(session.id)}</span>
        <span>所属项目：${escapeHtml(project ? project.name : "无项目会话")}</span>
        <span>访问模式：${escapeHtml(project ? getAccessModeHelpText(project.access_mode) : "当前会话不属于任何项目，按开放可访问历史处理。")}</span>
      </div>
      <label class="field-label" for="moveProjectSelect">移动到项目</label>
      <div class="inline-row">
        <select id="moveProjectSelect" class="select-input"></select>
        <button id="moveSessionButton" class="secondary-button" type="button">移动</button>
      </div>
      <div class="inline-row action-stack">
        <button id="archiveSessionButton" class="ghost-button" type="button">归档</button>
        <button id="deleteSessionButton" class="danger-button" type="button">删除会话</button>
      </div>
    </div>
  `;

  if (session.status === "archived") {
    elements.sessionBanner.className = "notice warning";
    elements.sessionBanner.textContent =
      "当前会话已归档。你仍可以查看信息，但聊天输入区会保持禁用。";
    return;
  }

  elements.sessionBanner.className = "notice hidden";
  elements.sessionBanner.textContent = "";
}

function renderConnectionBox(state, elements) {
  elements.healthBadge.className = `badge ${state.health.status || "neutral"}`;
  elements.healthBadge.textContent = state.health.label;
  elements.environmentValue.textContent = state.health.environment || "未连接";
  elements.backendBaseUrl.value = state.backendBaseUrl;
}

function renderProjectSelectOptions(state) {
  const moveSelect = document.querySelector("#moveProjectSelect");
  if (!moveSelect) {
    return;
  }

  moveSelect.innerHTML = [
    '<option value="">选择目标项目</option>',
    '<option value="__none__">移出项目，变成未归属会话</option>',
    ...state.projects.map(
      (project) =>
        `<option value="${project.id}">${escapeHtml(project.name)} (${escapeHtml(
          getAccessModeLabel(project.access_mode),
        )})</option>`,
    ),
  ].join("");
}

function renderNewChatMenu(state, elements) {
  const project = state.selectedProjectDetail;
  const isOpen = state.ui.newChatMenuOpen && Boolean(project);

  elements.newChatMenu.className = isOpen ? "floating-menu" : "floating-menu hidden";
  if (!isOpen) {
    elements.newChatMenu.innerHTML = "";
    return;
  }

  elements.newChatMenu.innerHTML = `
    <p class="floating-menu-copy">
      当前已选中项目 <strong>${escapeHtml(project.name)}</strong>。新聊天可以直接创建到该项目下，也可以先创建为未归属会话。
    </p>
    <div class="floating-menu-actions">
      <button id="createChatInProjectButton" class="secondary-button" type="button">创建到当前项目</button>
      <button id="createUnassignedChatButton" class="ghost-button" type="button">创建未归属会话</button>
    </div>
  `;
}

function renderProjectModal(state, elements) {
  elements.projectModal.className = state.ui.projectModalOpen
    ? "modal-shell"
    : "modal-shell hidden";
}

export function renderManagement(state, elements) {
  renderNotice(elements.globalNotice, state.notices.global);
  renderNotice(elements.projectNotice, state.notices.projects);
  renderNotice(elements.sessionNotice, state.notices.sessions);

  renderConnectionBox(state, elements);
  renderProjectsSection(state, elements);
  renderUnassignedSection(state, elements);
  renderCurrentSessionPanel(state, elements);
  renderProjectSelectOptions(state);
  renderNewChatMenu(state, elements);
  renderProjectModal(state, elements);

  const archiveButton = document.querySelector("#archiveSessionButton");
  const deleteButton = document.querySelector("#deleteSessionButton");
  const moveButton = document.querySelector("#moveSessionButton");
  const selectedSessionLocked = state.selectedSessionDetail?.status === "archived";
  const hasSelectedSession = Boolean(state.selectedSessionDetail);

  if (archiveButton) {
    archiveButton.disabled = !hasSelectedSession || selectedSessionLocked;
  }
  if (deleteButton) {
    deleteButton.disabled = !hasSelectedSession;
  }
  if (moveButton) {
    moveButton.disabled = !hasSelectedSession || selectedSessionLocked;
  }
}
