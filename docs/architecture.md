# Architecture

## 当前分层

当前仓库仍然是一个应用型 chat demo，而不是通用 Agent 平台。

核心结构：

- API Router
- Services
- ContextResolver
- Memory
- Search
- LLM
- DB Models
- Frontend Static Console

## 职责划分

### API Router

负责：

- 解析请求
- 调用 service
- 返回 response

### ChatService

负责聊天主流程编排：

1. 解析当前会话上下文
2. 判断是否触发搜索
3. 注入当前项目的 `name` / `instruction` / active `stable facts` 到模型 system context
4. 调用模型生成回复
5. 写回消息与会话记忆
6. 在不影响主聊天成功的前提下尝试自动命名会话

### ContextResolver

负责会话可读上下文解析：

- 当前会话 recent messages
- 当前会话 `working_memory`
- 当前会话所属项目的 `name` / `instruction`
- 当前会话所属项目的 active `stable facts`
- 按项目层与会话层规则筛选可读的其他会话 `session_digest`

### MemoryService

负责直接和记忆持久化相关的能力：

- 读取 recent messages
- 读取 / 保存 `working_memory`
- 读取 / 保存 `session_digest`
- `append_turn`
- `ChatMessage` / `SessionSummary` 的直接写入

### StableFactService

负责项目层长期稳定信息：

- 列出 / 创建 / 更新 / 删除 `ProjectStableFact`
- 通过 `status=active|archived` 管理是否参与聊天上下文
- 保持 stable facts 与消息历史、会话摘要分离

### SessionService

负责会话层基础管理能力：

- 创建 / 列表 / 查看 / 归档 / 删除 / 移动会话
- 读取会话完整消息历史
- 更新会话标题
- 在标题为空时生成稳定的默认标题

### ProjectService

负责项目管理：

- 创建 / 列表 / 查看 / 更新 / 删除项目
- 维护项目层 `name` / `instruction` / `description`

## 会话完整历史回读

新增的消息回读能力通过：

- `GET /api/sessions/{session_id}/messages`

实现路径是：

- Router -> `SessionService.get_session_messages()` -> `ChatMessage`

当前按时间正序返回，不做分页，优先满足前端刷新恢复与 demo 测试需求。

## 自动命名

自动命名不依赖额外的复杂工具层，也不要求在线模型可用。

当前流程：

1. 聊天成功写回消息后
2. `ChatService` 调用 `SessionService.maybe_generate_title()`
3. 如果会话没有标题，则基于第一条 user message 生成短标题
4. 如果自动命名失败，不影响聊天接口成功返回

## 前端恢复逻辑

前端当前会同时使用：

- `localStorage` 保存当前选中会话与侧边栏状态
- `GET /api/sessions/{session_id}/messages` 在刷新后重新拉取消息历史
- `GET /api/sessions/{session_id}/summary` 恢复当前会话 `working_memory` / `session_digest` 调试视图
- `GET /api/projects/{project_id}/stable-facts` 在项目编辑弹窗中实时读取 stable facts

因此右侧聊天区不再只依赖“本页生命周期内”的本地缓存。

## 未来扩展：Tool Layer（预留）

当前 service 不等于 tool。

如果后续进入 agent 化阶段，计划新增独立 `backend/app/tools/` 作为扩展层。该层应当是 service 的薄包装，而不是重复实现业务逻辑。

原则：

1. tool 不重复实现业务逻辑
2. tool 优先调用 service，不直接操作数据库
3. 当前聊天主流程不依赖 tool 层
4. tool 层属于未来扩展，不是当前 MVP 范围

## 会话层收口说明（补充）

当前会话层底座采用以下原则：

- `ChatMessage` 是 source of truth
- `SessionSummary` 是 derived artifact，其中区分 `working_memory` 和 `session_digest`
- `Project.instruction` 是项目级提示词，而不是访问边界字段
- `ProjectStableFact` 是项目层长期稳定信息层，不承担摘要缓存职责
- `is_private` 是会话级、可逆的可见性开关
- 会话记忆继续走规则压缩，暂不升级为每轮 LLM 摘要
- stable facts 当前只做人管控，不做自动抽取

对应到分层职责：

- `MemoryService` 负责消息写入、规则摘要维护，以及会话元数据同步更新
- `StableFactService` 负责项目级长期稳定信息 CRUD 与状态切换
- `SessionService` 负责会话元数据读取、标题更新、私密性更新
- `ContextResolver` 在读取其他会话时遵守最新的 `is_private` 值，并在当前项目存在时读取 active stable facts

这也意味着：

- UI 中展示的 summary 只是内部调试视图，不是主对象
- stable facts 不是消息历史回放入口，而是项目层长期信息输入
- 如果 summary 缓存异常，未来应允许回源到 `ChatMessage` 重建
- 当前仍然不做跨会话完整消息级读取，也不做 embedding memory / 全文检索

## 项目级 instruction 与 stable facts

当前项目层同时承担三种不同角色：

- `access_mode`：决定跨项目 / 跨会话边界
- `instruction`：决定该项目下聊天的默认行为提示
- `stable facts`：提供项目层长期稳定信息

三者在主链路中是分开的：

1. `ContextResolver` 解析当前会话所属项目
2. `ChatService` 把 `project.name`、`project.instruction` 和 active `stable facts` 传给 `LLMService`
3. `LLMService` 以独立 system message 注入项目级上下文
4. `working_memory` / `session_digest` 继续按会话记忆层独立注入
5. `access_mode` 继续只影响访问边界，不参与提示词语义
