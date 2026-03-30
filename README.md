# memory-search-chat-demo

一个面向学习与演示的最小可运行聊天应用 Demo，当前重点是把“多轮对话 + 会话记忆 + 搜索 + 项目/会话管理 + 受控跨会话上下文”串起来，并保持结构清晰、方便继续迭代。

## 当前能力

- 已有 `POST /api/chat` 聊天接口
- 已有 SQLite 持久化的 `ChatSession` / `ChatMessage` / `SessionSummary` / `Project`
- 已有会话摘要记忆与搜索触发逻辑
- 已有项目与会话管理 API
- 已把项目层 `scope_mode`、`is_isolated` 和会话层 `is_private` / `status` 接入聊天上下文解析

## 当前阶段说明

当前已经完成：

- 阶段 1：项目层 + 会话层权限的数据模型与管理 API
- 阶段 2：两层权限规则接入聊天上下文解析

当前仍未完成：

- allowlist
- 向量库检索
- 更复杂的跨会话召回排序
- 项目管理前端 UI

## 当前聊天上下文规则

聊天时会进入模型上下文的数据：

- 当前会话最近消息
- 当前会话摘要
- 按权限规则筛出的其他会话摘要
- 搜索结果（若触发）

当前不会进入模型上下文的数据：

- 其他会话完整原始消息
- private 会话摘要
- deleted 会话
- archived 会话
- 被 isolated 项目边界挡住的跨项目摘要

## 权限规则摘要

- 项目层决定默认边界
- 会话层只能收紧，不能放宽
- `conversation_only`：只读当前会话
- `project_only`：读当前会话 + 同项目可访问摘要
- `project_plus_global`：在项目内基础上补全局可访问摘要
- `global`：读所有允许访问的摘要
- `global` 也不会绕过 `private`、`deleted`、`archived`、`is_isolated`

## API 概览

### 聊天接口

- `POST /api/chat`

聊天响应当前包含两个轻量调试字段：

- `context_scope`
- `related_summary_count`

### 项目管理接口

- `POST /api/projects`
- `GET /api/projects`
- `GET /api/projects/{project_id}`

### 会话管理接口

- `POST /api/sessions`
- `GET /api/sessions`
- `GET /api/sessions/{session_id}`
- `POST /api/sessions/{session_id}/archive`
- `DELETE /api/sessions/{session_id}`
- `POST /api/sessions/{session_id}/move`

## 测试

运行当前最小测试集：

```bash
pytest tests/test_context_rules.py tests/test_management_api.py tests/test_chat_api.py tests/test_services.py -q
```

## 文档

更详细说明见：

- `docs/project-plan.md`
- `docs/architecture.md`
- `docs/api.md`
- `docs/dev-notes.md`

## License

本项目采用 [MIT License](./LICENSE)。
