# Architecture

## 当前结构

```text
Browser
  |
  v
Frontend (HTML / CSS / JavaScript)
  |
  v
FastAPI
  |
  v
API Router
  |------> /api/chat
  |------> /api/projects
  `------> /api/sessions
         |
         v
ChatService
  |------> ContextResolver
  |------> MemoryService
  |------> SearchService
  `------> LLMService

Projects Router ------> ProjectService
Sessions Router ------> SessionService
         |
         v
SQLite
```

## 分层说明

### Frontend

前端是一个纯静态 Web 测试控制台，负责：

- 管理项目和会话
- 选择当前项目 / 当前会话
- 发起聊天请求
- 展示回复、摘要、搜索来源和调试字段

### API Router

API 层继续保持轻量，主要负责：

- 解析请求参数
- 调用对应 service
- 返回 schema response

当前路由分成三类：

- `chat.py`
  聊天入口
- `projects.py`
  项目管理接口
- `sessions.py`
  会话管理接口

### ChatService

`ChatService` 仍然保持轻量编排，只负责：

- 确定 `session_id`
- 调用 `ContextResolver` 获取可访问上下文
- 调用搜索服务
- 调用模型服务
- 调用 `MemoryService.append_turn()` 写回消息和摘要
- 返回轻量调试信息

权限判断和上下文拼装不再堆在 `ChatService` 内部。

### MemoryService

`MemoryService` 现在只负责会话记忆读写：

- 当前会话最近消息读取
- 当前会话摘要读取
- 追加消息并更新摘要
- `ChatMessage` / `SessionSummary` 直接持久化逻辑

### ContextResolver

`ContextResolver` 负责聊天上下文解析：

- 按项目 `scope_mode` 计算默认边界
- 按会话 `is_private` 进一步收紧
- 按项目 `is_isolated` 阻止跨边界读取
- 过滤 deleted / archived / private 的外部候选会话
- 把其他会话以摘要形式组装进上下文

这层拆出来后，后续继续加 allowlist、调试接口和召回排序会更自然。

### ProjectService / SessionService

这两个 service 负责项目与会话管理的核心操作：

- `ProjectService`
  创建 / 列表 / 单查项目
- `SessionService`
  创建 / 列表 / 单查 / 归档 / 软删除 / 移动会话

router 里不再直接堆 DB 查询和状态变更逻辑。

## 数据模型关系

```text
Project 1 --- N ChatSession 1 --- N ChatMessage
                         |
                         `--- 1 SessionSummary
```

### Project

关键字段：

- `scope_mode`
  决定项目内会话默认的上下文边界
- `is_isolated`
  决定该项目是否允许被项目外会话跨边界读取
- `status`
  项目生命周期状态

### ChatSession

关键字段：

- `project_id`
  会话归属项目
- `status`
  会话生命周期状态
- `is_private`
  会话层收紧规则

## 当前权限规则

### 设计原则

- 项目层决定默认边界
- 会话层只能收紧，不能放宽
- `is_private=true` 时，默认只有当前会话自己可读
- `is_isolated=true` 时，不能跨越该项目边界读取内容
- `scope_mode=global` 代表“读取所有允许访问的历史”，不是“无条件读取所有历史”

### 实际解析规则

#### conversation_only

只读取：

- 当前会话最近消息
- 当前会话摘要

#### project_only

读取：

- 当前会话最近消息
- 当前会话摘要
- 同项目下其他非 private、非 deleted、当前实现中也要求 `status=active` 的会话摘要

不读取：

- 项目外摘要
- 其他会话原始消息

#### project_plus_global

读取：

- 当前会话最近消息
- 当前会话摘要
- 同项目可访问会话摘要
- 项目外可访问的全局摘要

限制：

- 不读取 private
- 不读取 deleted
- 当前实现中不读取 archived
- 不能跨过 isolated 项目边界

#### global

读取：

- 当前会话最近消息
- 当前会话摘要
- 所有允许访问的其他会话摘要

限制同样成立：

- private 不可读
- deleted 不可读
- archived 当前不纳入检索
- isolated 项目边界不可穿透

## 当前会进入模型上下文的数据

- 当前会话最近消息
- 当前会话摘要
- `ContextResolver` 解析出的相关会话摘要
- 搜索结果（若触发搜索）

## 当前不会进入模型上下文的数据

- 其他会话完整消息历史
- private 会话摘要
- deleted 会话摘要
- archived 会话摘要
- 被 isolated 边界挡住的跨项目摘要

## 当前实现的取舍

- 为了保持 demo 简洁，跨会话只拼摘要，不做向量检索
- archived 会话暂不纳入上下文，避免语义复杂化
- allowlist 尚未实现，只保留未来扩展空间
- 外部候选摘要目前保持轻量排序，优先同项目，再补全全局可访问摘要
