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
- 当前会话自己的 recent messages 和 `working_memory` 始终优先进入上下文
- 其他会话当前只以 `session_digest` 参与上下文，不读取完整原始消息
- 如果当前会话属于项目，会额外注入 `project.name`、`project.instruction` 和项目 active `stable facts`
- `stable facts` 是长期稳定信息层，不是消息历史，也不是聊天摘要
- `archived` 会话不能继续聊天
- allowlist 仍未实现

当前 system context 顺序：

1. 全局 `SYSTEM_PROMPT`
2. `project.name` + `project.instruction`
3. 项目 active `stable facts`
4. 当前会话 `working_memory`
5. 相关会话 `session_digest`
6. 搜索上下文
7. recent messages

响应示例：

```json
{
  "session_id": "8d4e5c7c5e954a5fa9f6d8f7567dc001",
  "reply": "demo reply",
  "title": "hello demo",
  "working_memory": null,
  "session_digest": "User: hello demo | Assistant: demo reply",
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
  本次注入到上下文中的其他会话 `session_digest` 数量

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
  "instruction": "Always answer like a product copilot.",
  "description": "optional human-readable description",
  "access_mode": "project_only"
}
```

字段语义：

- `name`：项目主题名，弱提示
- `instruction`：项目级行为指令，会在该项目下聊天时进入 system context
- `description`：给人看的项目说明，不作为主提示词
- `access_mode`：访问边界控制，不负责提示词语义

### GET /api/projects

列出项目，响应中包含 `instruction`。

### GET /api/projects/{project_id}

查看单个项目，响应中包含 `instruction`。

### PATCH /api/projects/{project_id}

更新项目。当前只允许修改：`name`、`instruction`、`description`。`access_mode` 创建后不可修改。

请求体示例：

```json
{
  "instruction": "Default to Chinese and keep answers concise.",
  "description": "新的项目说明"
}
```

### DELETE /api/projects/{project_id}

硬删除项目，并级联删除项目内全部会话、消息、摘要和 stable facts。

## 项目 stable facts 接口

### GET /api/projects/{project_id}/stable-facts

列出某个项目的 stable facts。

查询参数：

- `include_archived`，默认 `false`

默认只返回 `active` 条目。

### POST /api/projects/{project_id}/stable-facts

创建项目 stable fact。

请求体：

```json
{
  "content": "User prefers concise Chinese answers."
}
```

### PATCH /api/projects/{project_id}/stable-facts/{fact_id}

更新 stable fact 内容或状态。

请求体示例：

```json
{
  "content": "User prefers concise Chinese answers with action items.",
  "status": "active"
}
```

停用 stable fact：

```json
{
  "status": "archived"
}
```

### DELETE /api/projects/{project_id}/stable-facts/{fact_id}

硬删除 stable fact。

### stable fact 语义说明

- `stable facts` 是项目层长期稳定信息层
- 适合保存长期偏好、明确确认的事实、长期有效约束
- 只有 `active` 条目会在聊天时注入上下文
- 它不是 `ChatMessage` 历史
- 它不是 `working_memory`
- 它不是 `session_digest`

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

更新会话信息，当前支持修改标题和私密性。

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

### GET /api/sessions/{session_id}/summary

返回当前会话的内部派生记忆，用于前端在刷新后恢复调试展示。

示例响应：

```json
{
  "session_id": "abc123",
  "working_memory": "User: ... | Assistant: ...",
  "session_digest": "Started with: ... || Current state: ...",
  "summary_updated_at": "2026-03-31T12:34:56Z"
}
```

说明：

- `working_memory` 可能为 `null`，表示当前会话暂时还没有可用的旧窗口工作记忆。
- `session_digest` 可能为 `null`，表示当前会话暂时还没有可用的会话级摘要。
- 该接口返回的是派生缓存，而不是事实源；真实历史仍以 `ChatMessage` 为准。

## 状态与枚举

### Project.access_mode

- `open`
- `project_only`

### ChatSession.is_private

- `false` 表示 shared
- `true` 表示 private

### Project.status / ChatSession.status / ProjectStableFact.status

- `active`
- `archived`

## 当前未实现

当前仍未实现：

- allowlist
- stable facts 自动抽取
- 向量库检索
- 其他会话完整消息拼接
- 更复杂的召回排序与打分
