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
3. 调用模型生成回复
4. 写回消息与 summary
5. 在不影响主聊天成功的前提下尝试自动命名会话

### ContextResolver

负责会话可读上下文解析：

- 当前会话 recent messages
- 当前会话 summary
- 按项目层与会话层规则筛选可读的其他会话 summary

### MemoryService

负责直接和记忆持久化相关的能力：

- 读取 recent messages
- 读取 / 保存 summary
- `append_turn`
- `ChatMessage` / `SessionSummary` 的直接写入

### SessionService

负责会话层基础管理能力：

- 创建 / 列表 / 查看 / 归档 / 删除 / 移动会话
- 读取会话完整消息历史
- 更新会话标题
- 在标题为空时生成稳定的默认标题

### ProjectService

负责项目管理：

- 创建 / 列表 / 查看 / 删除项目

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

- `localStorage` 保存当前选中会话与已缓存消息
- `GET /api/sessions/{session_id}/messages` 在刷新后重新拉取消息历史

因此右侧聊天区不再只依赖“本页生命周期内”的本地缓存。

## 未来扩展：Tool Layer（预留）

当前 service 不等于 tool。

如果后续进入 agent 化阶段，计划新增独立 `backend/app/tools/` 作为扩展层。该层应当是 service 的薄包装，而不是重复实现业务逻辑。

原则：

1. tool 不重复实现业务逻辑
2. tool 优先调用 service，不直接操作数据库
3. 当前聊天主流程不依赖 tool 层
4. tool 层属于未来扩展，不是当前 MVP 范围
