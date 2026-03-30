# memory-search-chat-demo

一个面向学习与演示的最小可运行聊天应用 Demo，当前重点是把“多轮对话 + 会话记忆 + 搜索 + 项目/会话管理 + 受控跨会话上下文”串起来，并保持结构清晰、方便继续迭代。

## 当前能力

- 已有 `POST /api/chat` 聊天接口
- 已有 SQLite 持久化的 `ChatSession` / `ChatMessage` / `SessionSummary` / `Project`
- 已有项目与会话管理 API
- 已把项目层 `access_mode` 和会话层 `is_private` / `status` 接入聊天上下文解析
- 前端已改造成可直接测试项目 / 会话 / 访问规则的纯静态 Web 控制台
- 后端 service 已做轻量拆分，便于继续加 allowlist、召回排序和调试接口

## 当前阶段说明

当前已经完成：

- 阶段 1：项目层 + 会话层权限的数据模型与管理 API
- 阶段 2：两层权限规则接入聊天上下文解析
- 阶段 3：前端改造成可测试项目 / 会话 / 权限规则的 Web 控制台
- 后端轻量优化：拆分上下文解析与项目 / 会话管理 service
- 权限模型重写：改为 `Project.access_mode` + `ChatSession.is_private`

当前仍未完成：

- allowlist
- 向量库检索
- 更复杂的跨会话召回排序

当前版本仍以应用后端服务为主。
后续如果进入 agent 化阶段，计划新增独立 `tools/` 层作为扩展，用薄包装方式复用现有 service，而不影响当前 service 结构。

## 新的权限模型

### 项目层

项目只控制跨项目边界：

- `open`
  项目内会话可以访问外部可访问历史，项目内非 private 会话也可以被项目外访问
- `project_only`
  项目内会话只能访问本项目内历史，项目内会话内容对项目外不可见

### 会话层

会话仍保留 `is_private`，但语义改为：

- `false`
  shared，会话可以被其他允许访问的会话读取
- `true`
  private，会话不能被其他会话读取

关键点：

- private 只影响“别人能不能读我”
- private 不影响“我能不能读别人”

## 当前聊天上下文规则

聊天时会进入模型上下文的数据：

- 当前会话最近消息
- 当前会话摘要
- 按新规则筛出的其他会话摘要
- 搜索结果（若触发）

聊天时不会进入模型上下文的数据：

- 其他会话完整原始消息
- private 会话摘要
- archived 会话
- deleted 会话

`context_scope` 调试字段当前只反映两种语义：

- `open`
- `project_only`

前端调试区会继续显示 `context_scope` 字段名，但现在按“访问模式解析结果”来理解，而不是旧版四档 scope 语义。

## 本地 SQLite 说明

如果你的本地 SQLite 文件来自旧版 `scope_mode / is_isolated` 语义，当前代码会尽量补充 `access_mode` 字段并做一次轻量映射。

但这类旧数据的语义无法完全无损迁移。
如果你希望严格按新产品规则验证行为，建议删除旧的本地 SQLite 文件后重新初始化。

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
2. 左侧“项目”板块头部用“新项目”创建项目，选择“项目访问模式”：`开放项目（open）` 或 `仅限项目（project_only）`
3. 左侧用“新聊天”创建会话；如果当前已选中项目，可以选择创建到当前项目或创建成未归属会话
4. 在左侧项目树或“未归属会话”板块里切换当前会话，再到右侧发送消息
5. 在右侧观察“当前项目访问模式”“当前会话可见性”“context_scope（按新语义解释为访问模式解析结果）”“related_summary_count”、搜索状态和模型降级状态

说明：

- 当前未选中会话时，聊天区会禁止直接发送消息
- 当前会话若已 `archived` 或 `deleted`，聊天区也会明确禁用并提示原因
- 私密会话不会被其他会话访问，但它自己仍然可以访问其他允许访问的历史
- 无项目且非私密的会话，属于开放可访问历史的一部分，不会自动退化成只读自己
- 左侧导航栏只分“项目”和“未归属会话”两块，不再额外重复展示一份“全部聊天”
- 右侧页面现在以聊天主区为中心；summary、调试字段和快捷测试都被收进次级信息区，避免抢占聊天区视觉重心

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
