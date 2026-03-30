# API

当前 API 分为两部分：

- 聊天接口
- 项目 / 会话管理接口

本阶段的重点是：聊天接口已经接入项目层 + 会话层的上下文访问规则。

## 基础接口

### GET /health

返回服务健康状态。

响应示例：

```json
{
  "status": "healthy",
  "environment": "development"
}
```

## 聊天接口

### POST /api/chat

处理单轮聊天。

请求体：

```json
{
  "message": "hello demo",
  "session_id": "optional-session-id"
}
```

说明：

- `session_id` 不传时会自动创建新会话 ID
- 当前会话自己的最近消息仍然优先进入上下文
- 其他会话当前只以摘要形式参与上下文
- allowlist 仍未实现

响应示例：

```json
{
  "session_id": "8d4e5c7c5e954a5fa9f6d8f7567dc001",
  "reply": "demo reply",
  "summary": null,
  "used_live_model": false,
  "fallback_reason": "missing_api_key",
  "search_triggered": false,
  "search_used": false,
  "sources": [],
  "context_scope": "conversation_only",
  "related_summary_count": 0
}
```

新增调试字段：

- `context_scope`
  当前会话实际使用的上下文边界
- `related_summary_count`
  本次注入到上下文中的其他会话摘要数量

### 聊天上下文规则

#### conversation_only

只读当前会话最近消息和当前会话摘要。

#### project_only

读取：

- 当前会话最近消息
- 当前会话摘要
- 同项目下可访问的其他会话摘要

#### project_plus_global

读取：

- 当前会话最近消息
- 当前会话摘要
- 同项目可访问摘要
- 项目外可访问摘要

#### global

读取：

- 当前会话最近消息
- 当前会话摘要
- 所有允许访问的其他会话摘要

### 聊天上下文过滤条件

以下内容当前不会进入上下文：

- `is_private=true` 的其他会话
- `status=deleted` 的会话
- `status=archived` 的会话
- 被 `is_isolated=true` 项目边界阻止的跨项目会话
- 其他会话的完整原始消息

## 项目接口

### POST /api/projects

创建项目。

请求体：

```json
{
  "name": "Demo Project",
  "description": "optional",
  "scope_mode": "project_only",
  "is_isolated": true
}
```

### GET /api/projects

列出项目。

查询参数：

- `include_archived`，默认 `true`
- `include_deleted`，默认 `false`

### GET /api/projects/{project_id}

查看单个项目。

## 会话管理接口

### POST /api/sessions

创建会话。

请求体：

```json
{
  "title": "Project session",
  "project_id": 1,
  "is_private": true
}
```

### GET /api/sessions

列出会话。

查询参数：

- `project_id`
- `include_archived`，默认 `false`
- `include_deleted`，默认 `false`

### GET /api/sessions/{session_id}

查看单个会话。

### POST /api/sessions/{session_id}/archive

归档会话，把 `status` 改成 `archived`。

### DELETE /api/sessions/{session_id}

软删除会话，把 `status` 改成 `deleted`。

### POST /api/sessions/{session_id}/move

把会话移入某个项目。

请求体：

```json
{
  "project_id": 2
}
```

## 状态与枚举

### Project.scope_mode

- `conversation_only`
- `project_only`
- `project_plus_global`
- `global`

### Project.status / ChatSession.status

- `active`
- `archived`
- `deleted`

## 当前未实现

当前仍未实现：

- allowlist
- 向量库检索
- 其他会话完整消息拼接
- 更复杂的召回排序与打分
