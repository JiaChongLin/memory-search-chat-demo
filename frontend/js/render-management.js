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

function formatDateTime(value) {
  if (!value) {
    return "暂无";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "暂无";
  }

  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
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

function getStableFactsForProject(state, projectId) {
  if (!projectId) {
    return [];
  }
  return Array.isArray(state.stableFactMap[projectId]) ? state.stableFactMap[projectId] : [];
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
        ${session.is_private ? badge("私密", "danger") : badge("共享", "soft")}
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
  const instructionHint = project.instruction
    ? `<div class="sidebar-note compact">instruction：${escapeHtml(project.instruction)}</div>`
    : "";

  return `
    <article class="nav-project-group ${isSelected ? "selected" : ""}">
      <div class="nav-project-top">
        <button class="nav-project-main" type="button" data-project-select="${project.id}">
          <span class="nav-project-title-row">
            <strong>${escapeHtml(project.name)}</strong>
            <span class="nav-count">${sessions.length}</span>
          </span>
          <span class="nav-project-meta">
            ${badge(getAccessModeLabel(project.access_mode), "scope")}
            ${project.instruction ? badge("有指令", "soft") : ""}
          </span>
        </button>
        <div class="nav-project-actions">
          <button
            class="icon-button nav-inline-button"
            type="button"
            data-project-edit="${project.id}"
            title="编辑项目"
            aria-label="编辑项目"
          >
            编辑
          </button>
          ${
            isSelected
              ? `
                <button
                  class="icon-button nav-inline-button nav-delete-button"
                  type="button"
                  data-project-delete="${project.id}"
                  title="删除项目"
                  aria-label="删除项目"
                >
                  删除
                </button>
              `
              : ""
          }
        </div>
      </div>
      ${
        isExpanded
          ? `
            <div class="nav-project-children">
              ${instructionHint}
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
      <button id="openProjectModalButton" class="icon-button" type="button" title="新项目">＋</button>
    </div>
    ${
      collapsed
        ? ""
        : `
          <div class="sidebar-section-body">
            <div class="sidebar-note">项目访问模式决定跨项目边界；项目级 instruction 只负责聊天行为提示；stable facts 负责长期稳定信息层。</div>
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
            <div class="sidebar-note">这里只展示 project_id 为空的会话。</div>
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
  const stableFacts = getStableFactsForProject(state, project?.id);
  const activeStableFacts = stableFacts.filter((item) => item.status === "active");
  const projectInstruction = project?.instruction
    ? escapeHtml(project.instruction)
    : "当前项目未配置 instruction。";

  if (!session) {
    elements.sessionDetail.innerHTML = `
      <div class="session-side-card">
        <div class="mini-head">
          <h3>会话操作</h3>
          <span class="badge neutral">未选择</span>
        </div>
        <p class="detail-copy">选择会话后，这里会显示私密性切换、移动、归档和删除等操作。</p>
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
        <span>会话可见性：${escapeHtml(getPrivacyLabel(session.is_private))}</span>
        <span>消息数量：${escapeHtml(String(session.message_count ?? 0))}</span>
        <span>最后一条消息：${escapeHtml(formatDateTime(session.last_message_at))}</span>
      </div>
      <p class="hint-text">切换私密性只影响其他会话能否读取当前会话，不影响当前会话读取别人。</p>
      ${
        project
          ? `<p class="hint-text">项目级 instruction 会在聊天时注入 system context：${projectInstruction}</p>`
          : '<p class="hint-text">当前会话不属于任何项目，因此不会注入项目级 instruction。</p>'
      }
      ${
        project
          ? `<p class="hint-text">当前项目 active stable facts：${activeStableFacts.length} 条。它们属于长期稳定信息层，不等于消息历史，也不等于会话摘要。</p>`
          : '<p class="hint-text">当前会话没有项目容器，因此不会注入 stable facts。</p>'
      }
      <div class="inline-row action-stack">
        <button id="toggleSessionPrivacyButton" class="ghost-button" type="button">${session.is_private ? "设为共享" : "设为私密"}</button>
        <button id="archiveSessionButton" class="ghost-button" type="button">归档</button>
        <button id="deleteSessionButton" class="danger-button" type="button">删除会话</button>
      </div>
      <label class="field-label" for="moveProjectSelect">移动到项目</label>
      <div class="inline-row">
        <select id="moveProjectSelect" class="select-input"></select>
        <button id="moveSessionButton" class="secondary-button" type="button">移动</button>
      </div>
    </div>
  `;

  if (session.status === "archived") {
    elements.sessionBanner.className = "notice warning";
    elements.sessionBanner.textContent =
      "当前会话已归档。你仍然可以查看消息历史和内部摘要调试信息，但聊天输入区会保持禁用。";
    return;
  }

  elements.sessionBanner.className = "notice hidden";
  elements.sessionBanner.textContent = "";
}

function renderProjectSelectOptions(state) {
  const moveSelect = document.querySelector("#moveProjectSelect");
  if (!moveSelect) {
    return;
  }

  const currentProjectId = state.selectedSessionDetail?.project_id ?? null;
  const unassignedLabel =
    currentProjectId === null ? "当前：未归属会话" : "移出项目，变成未归属会话";

  moveSelect.innerHTML = [
    '<option value="">选择目标项目</option>',
    `<option value="__none__">${escapeHtml(unassignedLabel)}</option>`,
    ...state.projects.map(
      (project) =>
        `<option value="${project.id}">${escapeHtml(project.name)} (${escapeHtml(
          getAccessModeLabel(project.access_mode),
        )})</option>`,
    ),
  ].join("");

  moveSelect.value = currentProjectId === null ? "__none__" : String(currentProjectId);
}

function renderNewChatMenu(state, elements) {
  const project = state.selectedProjectDetail;
  const isOpen = state.ui.newChatMenuOpen;

  elements.newChatMenu.className = isOpen ? "floating-menu" : "floating-menu hidden";
  if (!isOpen) {
    elements.newChatMenu.innerHTML = "";
    return;
  }

  const headerCopy = project
    ? `当前已选中项目 <strong>${escapeHtml(project.name)}</strong>。可以创建共享或私密会话，并决定是否挂到当前项目下。`
    : "当前没有选中项目。可以先创建未归属会话，后续再移动到某个项目。";

  const currentProjectActions = project
    ? `
        <div class="floating-menu-group">
          <span class="floating-menu-label">当前项目</span>
          <p class="sidebar-note compact">${escapeHtml(project.instruction || "当前项目未配置 instruction。")}</p>
          <div class="floating-menu-actions">
            <button class="secondary-button" type="button" data-create-session-scope="current-project" data-create-session-private="false">共享会话</button>
            <button class="ghost-button" type="button" data-create-session-scope="current-project" data-create-session-private="true">私密会话</button>
          </div>
        </div>
      `
    : "";

  elements.newChatMenu.innerHTML = `
    <p class="floating-menu-copy">${headerCopy}</p>
    ${currentProjectActions}
    <div class="floating-menu-group">
      <span class="floating-menu-label">未归属会话</span>
      <div class="floating-menu-actions">
        <button class="secondary-button" type="button" data-create-session-scope="unassigned" data-create-session-private="false">共享会话</button>
        <button class="ghost-button" type="button" data-create-session-scope="unassigned" data-create-session-private="true">私密会话</button>
      </div>
    </div>
  `;
}

function renderStableFactList(state, editingProject) {
  if (!editingProject) {
    return '<div class="nav-empty">先创建项目，再维护 stable facts。</div>';
  }

  const facts = getStableFactsForProject(state, editingProject.id);
  if (!facts.length) {
    return '<div class="nav-empty">当前项目还没有 stable facts。可以先记录长期偏好、确认事实或长期约束。</div>';
  }

  return facts
    .map((fact) => {
      const statusBadge = fact.status === "active" ? badge("active", "success") : badge("archived", "warning");
      return `
        <article class="stable-fact-item ${fact.status === "archived" ? "is-archived" : ""}">
          <div class="mini-head compact">
            <div class="tag-row">
              ${statusBadge}
              <span class="stable-fact-time">更新于 ${escapeHtml(formatDateTime(fact.updated_at))}</span>
            </div>
          </div>
          <p class="stable-fact-content">${escapeHtml(fact.content)}</p>
          <div class="stable-fact-actions">
            <button class="ghost-button" type="button" data-stable-fact-edit="${fact.id}">编辑</button>
            <button class="ghost-button" type="button" data-stable-fact-toggle="${fact.id}">${fact.status === "active" ? "停用" : "启用"}</button>
            <button class="danger-button" type="button" data-stable-fact-delete="${fact.id}">删除</button>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderProjectModal(state, elements) {
  const isOpen = state.ui.projectModalOpen;
  const mode = state.ui.projectModalMode || "create";
  const editingProject = state.projects.find(
    (project) => project.id === state.ui.editingProjectId,
  ) || null;
  const stableFacts = getStableFactsForProject(state, editingProject?.id);
  const activeStableFacts = stableFacts.filter((item) => item.status === "active");
  const editingStableFact = stableFacts.find((item) => item.id === state.ui.editingStableFactId) || null;
  const stableFactsEnabled = mode === "edit" && Boolean(editingProject);

  elements.projectModal.className = isOpen ? "modal-shell" : "modal-shell hidden";

  if (elements.projectModalTitle) {
    elements.projectModalTitle.textContent = mode === "edit" ? "编辑项目" : "新建项目";
  }
  if (elements.projectSubmitButton) {
    elements.projectSubmitButton.textContent = mode === "edit" ? "保存修改" : "创建项目";
  }
  if (elements.projectModeHint) {
    elements.projectModeHint.textContent =
      mode === "edit"
        ? "项目访问模式创建后不可修改，这里仅展示当前模式。"
        : "创建后项目访问模式当前不支持修改。";
  }
  if (elements.projectAccessSelect) {
    elements.projectAccessSelect.disabled = mode === "edit";
  }
  if (elements.projectAccessReadonly) {
    elements.projectAccessReadonly.className =
      mode === "edit" ? "hint-text modal-readonly-note" : "hint-text modal-readonly-note hidden";
    elements.projectAccessReadonly.textContent = editingProject
      ? `当前访问模式：${getAccessModeLabel(editingProject.access_mode)} (${getAccessModeHelpText(editingProject.access_mode)})`
      : "";
  }
  if (elements.projectStableFactsBadge) {
    elements.projectStableFactsBadge.className = `badge ${stableFactsEnabled ? "soft" : "neutral"}`;
    elements.projectStableFactsBadge.textContent = stableFactsEnabled
      ? `${activeStableFacts.length} active / ${stableFacts.length} total`
      : "创建后可用";
  }
  if (elements.projectStableFactsHint) {
    elements.projectStableFactsHint.textContent = stableFactsEnabled
      ? "stable facts 是长期稳定信息层。只有 active 条目会在该项目下聊天时注入 system context；它们不等于消息历史，也不等于 working_memory / session_digest。"
      : "stable facts 挂在项目层。请先创建项目，再记录长期稳定偏好、确认事实或长期约束。";
  }
  if (elements.projectStableFactsList) {
    elements.projectStableFactsList.innerHTML = renderStableFactList(state, editingProject);
  }
  if (elements.stableFactEditorLabel) {
    elements.stableFactEditorLabel.textContent = editingStableFact
      ? "编辑 stable fact"
      : "新增 stable fact";
  }
  if (elements.stableFactInput) {
    elements.stableFactInput.disabled = !stableFactsEnabled;
    elements.stableFactInput.placeholder = stableFactsEnabled
      ? "例如：默认输出简洁结论；用户长期偏好中文；预算上限长期保持在 5000 元内。"
      : "请先创建项目，再维护 stable facts。";
  }
  if (elements.stableFactSubmitButton) {
    elements.stableFactSubmitButton.disabled = !stableFactsEnabled;
    elements.stableFactSubmitButton.textContent = editingStableFact ? "更新 stable fact" : "保存 stable fact";
  }
  if (elements.stableFactCancelButton) {
    elements.stableFactCancelButton.disabled = !stableFactsEnabled || !editingStableFact;
    elements.stableFactCancelButton.className =
      !stableFactsEnabled || !editingStableFact
        ? "ghost-button hidden"
        : "ghost-button";
  }
}

export function renderManagement(state, elements) {
  renderNotice(elements.globalNotice, state.notices.global);
  renderNotice(elements.projectNotice, state.notices.projects);
  renderNotice(elements.sessionNotice, state.notices.sessions);

  renderProjectsSection(state, elements);
  renderUnassignedSection(state, elements);
  renderCurrentSessionPanel(state, elements);
  renderProjectSelectOptions(state);
  renderNewChatMenu(state, elements);
  renderProjectModal(state, elements);

  const archiveButton = document.querySelector("#archiveSessionButton");
  const deleteButton = document.querySelector("#deleteSessionButton");
  const moveButton = document.querySelector("#moveSessionButton");
  const privacyButton = document.querySelector("#toggleSessionPrivacyButton");
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
  if (privacyButton) {
    privacyButton.disabled = !hasSelectedSession;
  }
}
