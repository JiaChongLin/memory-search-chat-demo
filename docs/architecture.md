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
  |------> MemoryService
  |------> SearchService
  `------> LLMService
         |
         v
SQLite
```

## 分层说明

### Frontend

前端仍然是轻量 demo 页面，负责：

- 发送聊天请求
- 维护当前 `session_id`
- 展示回复、摘要、搜索来源

当前还没有项目管理 UI，也没有可视化权限调试页。

### API Router

API 层当前分成三类路由：

- `chat.py`
  聊天入口
- `projects.py`
  项目管理接口
- `sessions.py`
  会话管理接口

### ChatService

`ChatService` 仍保持轻量编排，只负责：

- 确定 `session_id`
- 调用 `MemoryService.resolve_context()` 获取可访问上下文
- 调用搜索服务
- 调用模型服务
- 保存本轮消息和摘要
- 返回轻量调试信息

权限判断主逻辑没有塞进 `ChatService`，而是集中在 `MemoryService`。

### MemoryService

`MemoryService` 现在承担两类职责：

- 记忆读写
  - 当前会话最近消息
  - 当前会话摘要
  - 追加消息并更新摘要
- 上下文解析
  - 按项目 `scope_mode` 确定默认边界
  - 按会话 `is_private` 进一步收紧
  - 按项目 `is_isolated` 阻止跨边界读取
  - 过滤 deleted / archived / private 的外部候选会话
  - 把其他会话以摘要形式注入上下文

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
- `MemoryService` 解析出的相关会话摘要
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
- 对外部候选摘要的排序目前保持轻量，优先同项目，再补全局可访问摘要
