# memory-search-chat-demo

一个面向学习与演示的最小可运行聊天应用 Demo，当前重点是把“多轮对话 + 会话记忆 + 搜索 + 项目/会话管理 + 受控跨会话上下文”串起来，并保持结构清晰、方便继续迭代。

## 当前能力

- 已有 `POST /api/chat` 聊天接口
- 已有 SQLite 持久化的 `ChatSession` / `ChatMessage` / `SessionSummary` / `Project`
- 已有项目与会话管理 API
- 已把项目层 `scope_mode`、`is_isolated` 和会话层 `is_private` / `status` 接入聊天上下文解析
- 前端已改造成可直接测试项目 / 会话 / 权限规则的纯静态 Web 控制台
- 后端 service 已做轻量拆分，便于继续加 allowlist、召回排序和调试接口

## 当前阶段说明

当前已经完成：

- 阶段 1：项目层 + 会话层权限的数据模型与管理 API
- 阶段 2：两层权限规则接入聊天上下文解析
- 阶段 3：前端改造成可测试项目/会话/权限规则的 Web 控制台
- 后端轻量优化：拆分上下文解析与项目/会话管理 service

当前仍未完成：

- allowlist
- 向量库检索
- 更复杂的跨会话召回排序

## 后端结构

当前后端的职责分布是：

- `ChatService`
  负责串联上下文解析、搜索、模型调用和写回
- `MemoryService`
  负责最近消息、summary 和消息持久化
- `ContextResolver`
  负责项目层 + 会话层边界下的上下文解析
- `ProjectService` / `SessionService`
  负责项目与会话管理 API 的核心操作

## Web 控制台可以做什么

前端页面现在可以直接测试：

- 创建项目并观察 `scope_mode` / `is_isolated`
- 创建会话、切换会话、归档、软删除、移动项目
- 创建 private 会话并观察它在权限规则里的影响
- 针对当前选中会话聊天
- 观察 `context_scope` 和 `related_summary_count`
- 观察 `used_live_model`、`fallback_reason`、`search_triggered`、`search_used`
- 查看搜索来源 `sources`

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

## 快速运行

### 1. 启动后端

```bash
uvicorn backend.app.main:app --reload
```

### 2. 启动前端静态文件服务

```bash
cd frontend
python -m http.server 5500
```

然后访问：

```text
http://127.0.0.1:5500
```

### 3. 在页面里测试

建议按这个顺序：

1. 右上角先检查后端连接
2. 左侧创建项目，选择不同 `scope_mode`
3. 中间创建会话，必要时勾选 `is_private`
4. 先显式选中一个会话，再到右侧发送消息
5. 在右侧观察 `context_scope`、`related_summary_count`、搜索状态和模型降级状态

说明：

- 当前未选中会话时，聊天区会禁止直接发送消息
- 当前会话若已 `archived` 或 `deleted`，聊天区也会明确禁用并提示原因

## 测试

运行当前后端最小测试集：

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
