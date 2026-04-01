# memory-search-chat-demo

一个面向学习与演示的最小可运行聊天应用 Demo，当前重点是把“多轮对话 + 会话记忆 + 搜索 + 项目/会话管理 + 受控跨会话上下文”串起来，并保持结构清晰、方便继续迭代。

## 当前能力

- `POST /api/chat` 聊天接口
- SQLite 持久化的 `Project` / `ChatSession` / `ChatMessage` / `SessionSummary` / `ProjectStableFact`
- 项目与会话管理 API
- 项目名称 / 项目级 instruction / 描述编辑（`access_mode` 创建后不可修改）
- 项目级 stable facts / saved memories 管理
- 基于 `Project.access_mode` 与 `ChatSession.is_private` 的上下文读取规则
- 纯静态 Web 控制台，可测试项目、会话、聊天与调试字段
- 会话完整消息历史回读
- 会话自动命名
- 会话手动改名

## 当前权限模型

### 项目层

- `open`
  项目内会话可以访问外部可访问历史，且项目内非私密会话也可被项目外访问。
- `project_only`
  项目内会话只能访问本项目内历史，且项目内会话对项目外不可见。

### 会话层

- `is_private = false`
  共享会话，可被其他允许访问的会话读取。
- `is_private = true`
  私密会话，不能被其他会话读取，但自己仍然可以读取其他允许访问的历史。

### 生命周期

- `active`
- `archived`

`archived` 会话仍可查询，但不能继续聊天，也不会进入上下文检索。

## 会话能力补全

### 1. 完整历史回读

现在支持：

- `GET /api/sessions/{session_id}/messages`

用于返回该会话完整消息历史，按时间正序排列，当前不做分页。前端会在切换会话时主动回读历史，因此刷新页面后只要当前会话仍存在，就可以恢复消息列表。

### 2. 自动命名

当会话 `title` 为空时，第一次成功聊天后会自动补标题。

当前采用稳定的规则生成策略：

- 优先使用第一条 user message
- 自动压缩空白和换行
- 优先截取第一句
- 控制标题长度，过长时用省略号收尾
- 如果已有手动标题，不会被覆盖

### 3. 手动改名

现在支持：

- `PATCH /api/sessions/{session_id}`

当前只更新 `title`。前端右侧会话头部提供轻量改名入口，改名成功后会同步更新左侧导航与右侧标题。

## 项目级 instruction

项目层现在区分三类语义：

- `name`：项目主题名，弱提示
- `instruction`：项目级行为指令，会在该项目下会话聊天时注入 system context
- `description`：给人看的项目说明，不作为主提示词

## 项目级 stable facts / saved memories

项目层现在还有一层独立的长期稳定信息对象：

- `ProjectStableFact`
- 适合记录长期偏好、明确确认的事实、长期有效约束
- 只在所属项目聊天时按 `active` 条目注入上下文
- 不属于 `ChatMessage` 历史
- 不等于 `working_memory`
- 不等于 `session_digest`

换句话说：

- `ChatMessage` 是真实历史 source of truth
- `working_memory` 是当前会话续聊用的运行时工作记忆
- `session_digest` 是给其他会话读取的会话级对外摘要
- `stable facts` 是项目层长期稳定信息层

## 当前聊天上下文顺序

聊天主链路中的上下文顺序现在是：

1. 全局 `SYSTEM_PROMPT`
2. 当前会话所属项目的 `project.name` + `project.instruction`
3. 当前项目 active `stable facts`
4. 当前会话 `working_memory`
5. 相关会话 `session_digest`
6. 搜索上下文
7. recent messages

`access_mode` 继续只负责跨会话 / 跨项目边界，不负责提示词语义。

## 项目编辑

现在支持编辑项目的：

- `name`
- `instruction`
- `description`
- `stable facts`

当前不支持编辑：

- `access_mode`（项目访问模式创建后不可修改）

## 删除与归档规则

- 会话归档：保留记录，状态变为 `archived`
- 会话删除：硬删除，并级联删除该会话下的 `ChatMessage` 和 `SessionSummary`
- 项目删除：硬删除，并级联删除项目内全部会话、消息、摘要和 stable facts
- stable fact 停用：状态改为 `archived`，不再注入聊天上下文
- 当前不提供项目归档

## 前端恢复逻辑

前端当前会把以下状态保存在 `localStorage`：

- `backendBaseUrl`
- `currentProjectId`
- `currentSessionId`
- 左侧折叠与展开状态

页面刷新后：

1. 恢复当前选中的 `currentSessionId`
2. 重新拉取会话列表
3. 如果该会话仍存在，自动请求 `GET /api/sessions/{session_id}/messages`
4. 将完整历史写回前端本地状态并渲染到右侧聊天区
5. 当前会话的 `working_memory` / `session_digest` 通过 `GET /api/sessions/{session_id}/summary` 恢复调试展示

## 本地 SQLite 说明

如果你的本地 SQLite 文件来自更早的旧版本，建议删除旧数据库后重新初始化。

原因：

- 项目访问模式与上下文规则已经过重写
- 会话记忆已经拆成 `working_memory` + `session_digest`
- 项目层新增了 `instruction` 与 `stable facts`
- 旧库可能无法完全体现当前规则

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

## 测试

```bash
pytest tests/test_context_rules.py tests/test_management_api.py tests/test_chat_api.py tests/test_services.py -q
```

## 前端补充说明

- 前端默认直接使用本地开发后端地址，连接配置入口已从页面 UI 中移除。
- 页面启动时仍会静默执行 health check，但不再在左侧显示单独的连接状态面板。
- 右侧输入框现在是单行起步、自动增高的聊天输入区；超过最大高度后会在输入框内部滚动，发送后会恢复默认高度。
- 左侧项目区现在支持编辑项目名称、instruction、description 和项目级 stable facts。
- 删除项目和删除会话现在使用页面内自定义确认弹窗，不再使用浏览器默认确认框。
- 创建 / 更新 / 删除这类成功提示当前会短暂显示后淡出，避免常驻占位。
- 前端已减少无意义重渲染；在页面中选择文本后，鼠标松开不应再把选区立即清掉。

## 文档

- `docs/project-plan.md`
- `docs/architecture.md`
- `docs/api.md`
- `docs/dev-notes.md`

## License

本项目采用 [MIT License](./LICENSE)。

## 会话层设计原则（补充）

- `ChatMessage` 是 source of truth，真实历史以消息表为准。
- `SessionSummary` 是 derived artifact，只是内部派生缓存，不是事实源。
- `SessionSummary` 当前区分 `working_memory` 和 `session_digest` 两种语义。
- `ProjectStableFact` 是项目层长期稳定信息，不承担消息历史或摘要缓存职责。
- `is_private` 是会话级可见性开关，而且是可逆的。
- `is_private` 只影响“其他会话能否读取该会话”，不影响“该会话读取别人”。
- 当前 summary 继续采用规则压缩，不把每轮摘要改成 LLM 调用。
- 当前 stable facts 不做自动抽取，先以人工维护为主。

## 已实现的会话层能力（补充）

- 会话元数据：`message_count`、`last_message_at`、`summary_updated_at`
- 会话完整历史回读：`GET /api/sessions/{session_id}/messages`
- 会话自动命名与手动改名
- 会话私密性可逆切换：`PATCH /api/sessions/{session_id}` 支持更新 `title` 和 `is_private`
- 前端可创建共享 / 私密会话，并可切换当前会话的私密性

## 当前会话记忆展示策略

- `working_memory` 默认不作为主界面核心对象。
- `session_digest` 也只在调试/折叠区域中展示，避免和真实消息历史并列成主对象。
- `stable facts` 在项目编辑区域中管理，默认不和聊天消息并列展示。
- 如果需要追溯真实对话，应以 `ChatMessage` 历史为准。

## Session Layer Backlog

- summary 校验与回源重建
- 消息分页 / 懒加载
- 会话搜索
- 更强的摘要策略
- summary 版本管理
- stable facts 自动抽取与确认流
- 跨会话完整消息级读取（暂不做）
- embedding memory / 全文检索（暂不做）

## 前端恢复与提示行为补充

- 当前前端刷新后会继续恢复 `currentProjectId`、`currentSessionId` 和侧边栏 UI 状态。
- 当前会话的消息历史主要通过 `GET /api/sessions/{session_id}/messages` 回读恢复。
- 当前会话的 `working_memory` / `session_digest` 现在会通过 `GET /api/sessions/{session_id}/summary` 回读恢复，不再依赖把摘要长期写进 `localStorage`。
- 项目级 stable facts 当前不做额外本地缓存，项目弹窗打开时会实时从后端读取。
- 调试面板里的上下文快照仍然是当前页面内临时信息；刷新后不会从后端恢复，这属于当前设计，而不是缓存丢失 bug。
- 会话改名现在使用页面内轻量弹窗，不再使用浏览器原生 `prompt`。
- success / info 类型提示默认会短暂显示后淡出；warning / error 仍然保持可见，便于排查问题。
