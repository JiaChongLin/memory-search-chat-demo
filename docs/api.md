# API

当前 API 分为三部分：

- 基础接口
- 聊天接口
- 项目 / 会话管理接口

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
- 当前会话自己的 recent messages 和 summary 始终优先进入上下文
- 其他会话当前只以 summary 参与上下文，不读取完整原始消息
- `archived` 会话不能继续聊天
- allowlist 仍未实现

响应示例：

```json
{
  "session_id": "8d4e5c7c5e954a5fa9f6d8f7567dc001",
  "reply": "demo reply",
  "title": "hello demo",
  "summary": null,
  "used_live_model": false,
  "fallback_reason": "missing_api_key",
  "search_triggered": false,
  "search_used": false,
  "sources": [],
  "context_scope": "open",
  "related_summary_count": 0
}
```

调试字段：

- `context_scope`
  当前会话实际使用的访问模式，当前只有：`open` / `project_only`
- `related_summary_count`
  本次注入到上下文中的其他会话摘要数量

### 自动命名行为

当会话 `title` 为空时，第一次成功聊天后会自动补标题。

当前策略：

- 优先取第一条 user message
- 自动压缩换行和空白
- 优先取第一句
- 长度过长时做稳定截断
- 如果会话已有标题，不会被覆盖

## 项目接口

### POST /api/projects

创建项目。

请求体：

```json
{
  "name": "Demo Project",
  "description": "optional",
  "access_mode": "project_only"
}
```

### GET /api/projects

列出项目。

### GET /api/projects/{project_id}

查看单个项目。

### PATCH /api/projects/{project_id}

更新项目。当前只允许修改：`name`、`description`。`access_mode` 创建后不可修改。

请求体示例：

```json
{
  "name": "新的项目名称",
  "description": "新的项目描述"
}
```

### DELETE /api/projects/{project_id}

硬删除项目，并级联删除项目内全部会话、消息和摘要。

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

说明：

- `project_id` 可为空，表示无项目会话
- `is_private=true` 代表该会话不能被其他会话读取

### GET /api/sessions

列出会话。

查询参数：

- `project_id`
- `include_archived`，默认 `false`

### GET /api/sessions/{session_id}

查看单个会话。

### GET /api/sessions/{session_id}/messages

读取该会话完整消息历史，按时间正序返回。

响应示例：

```json
[
  {
    "id": 1,
    "session_id": "abc123",
    "role": "user",
    "content": "hello",
    "created_at": "2026-03-30T10:00:00Z"
  },
  {
    "id": 2,
    "session_id": "abc123",
    "role": "assistant",
    "content": "hi",
    "created_at": "2026-03-30T10:00:01Z"
  }
]
```

### PATCH /api/sessions/{session_id}

更新会话信息，当前只支持修改标题。

请求体：

```json
{
  "title": "新的会话标题"
}
```

### POST /api/sessions/{session_id}/archive

归档会话，把 `status` 改成 `archived`。

### DELETE /api/sessions/{session_id}

硬删除会话，并级联删除该会话下的消息和摘要。

### POST /api/sessions/{session_id}/move

把会话移入某个项目，或从项目中移出。

请求体：

```json
{
  "project_id": 2
}
```

移出项目时：

```json
{
  "project_id": null
}
```

## 状态与枚举

### Project.access_mode

- `open`
- `project_only`

### ChatSession.is_private

- `false` 表示 shared
- `true` 表示 private

### Project.status / ChatSession.status

- `active`
- `archived`

## 当前未实现

当前仍未实现：

- allowlist
- 向量库检索
- 其他会话完整消息拼接
- 更复杂的召回排序与打分

### GET /api/sessions/{session_id}/summary

返回当前会话的内部派生 summary，用于前端在刷新后恢复 summary 展示。

示例响应：

```json
{
  "session_id": "abc123",
  "summary": "用户: ... | 助手: ...",
  "summary_updated_at": "2026-03-31T12:34:56Z"
}
```

说明：
- `summary` 可能为 `null`，表示当前会话暂时还没有可用的内部摘要。
- 该接口返回的是 `SessionSummary` 这份派生缓存，而不是事实源；真实历史仍以 `ChatMessage` 为准。
