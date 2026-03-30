# Docs

`docs/` 目录记录项目设计、权限规则、接口说明和阶段计划。当前文档已经同步到新的权限模型：

- 项目层使用 `Project.access_mode`
- 会话层使用 `ChatSession.is_private`
- 前端控制台也已经改成按“项目访问模式 / 会话可见性”来展示和测试

## 文档索引

- `api.md`
  说明当前聊天接口、项目与会话管理接口，以及 `context_scope`、`related_summary_count` 等调试字段。
- `architecture.md`
  说明当前分层、`ContextResolver` 的职责、项目边界与会话可见性的判定方式，以及未来 Tool Layer 预留。
- `project-plan.md`
  记录阶段划分与当前进度，包含权限模型重写、前端控制台、后续 Tool Layer 预留等内容。
- `dev-notes.md`
  记录当前访问规则、旧 SQLite 到新模型的兼容说明，以及后续继续开发时的注意点。

## 当前状态

当前仓库已经完成：

- 会话级聊天、摘要记忆和搜索触发
- 项目与会话管理 API
- 基于 `access_mode + is_private` 的聊天上下文解析
- 可直接测试项目 / 会话 / 权限规则的纯静态 Web 控制台

当前仓库尚未完成：

- allowlist
- 向量库检索
- 更复杂的跨会话召回排序

如果你接下来要继续迭代，建议优先阅读：

- `project-plan.md`
- `architecture.md`
- `dev-notes.md`
