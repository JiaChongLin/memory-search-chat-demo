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

### ChatService

`ChatService` 保持轻量编排，只负责：

- 确定 `session_id`
- 调用 `ContextResolver` 获取可访问上下文
- 调用搜索服务
- 调用模型服务
- 调用 `MemoryService.append_turn()` 写回消息和摘要
- 返回轻量调试信息

### MemoryService

`MemoryService` 只负责会话记忆读写：

- 当前会话最近消息读取
- 当前会话摘要读取
- 追加消息并更新摘要
- `ChatMessage` / `SessionSummary` 直接持久化逻辑

### ContextResolver

`ContextResolver` 负责聊天上下文解析，核心规则是：

- 项目层决定跨项目边界
- 会话层决定该会话是否能被别人读取
- private 会话自己仍然可以读取其他允许访问的历史
- 当前会话始终优先读取自己的 recent messages 和 summary
- 其他会话当前只读取 summary

### ProjectService / SessionService

这两个 service 负责项目与会话管理的核心操作：

- `ProjectService`
  创建 / 列表 / 单查项目
- `SessionService`
  创建 / 列表 / 单查 / 归档 / 软删除 / 移动会话 / 移出项目

## 数据模型关系

```text
Project 1 --- N ChatSession 1 --- N ChatMessage
                         |
                         `--- 1 SessionSummary
```

### Project

关键字段：

- `access_mode`
  控制项目内会话是否允许访问项目外历史，以及该项目内容是否能被项目外读取
- `status`
  项目生命周期状态

### ChatSession

关键字段：

- `project_id`
  会话可不属于任何项目，也可以被移入或移出项目
- `status`
  会话生命周期状态
- `is_private`
  控制该会话是否可被其他会话读取，不控制它自己的读取权

## 当前权限模型

### 项目层：跨项目边界

#### open

- 当前会话可以访问外部可访问历史
- 项目内非 private 会话也可以被项目外访问

#### project_only

- 当前会话只能访问本项目内历史
- 项目内会话内容对项目外不可见

### 会话层：可见性

#### shared

当前实现中由 `is_private=false` 表示：

- 该会话可以被其他允许访问的会话读取
- 该会话自己也可以读取其他允许访问的历史

#### private

当前实现中由 `is_private=true` 表示：

- 该会话不能被任何其他会话读取
- 但该会话自己仍然可以读取其他允许访问的历史

## 当前会进入模型上下文的数据

- 当前会话最近消息
- 当前会话摘要
- `ContextResolver` 解析出的相关会话摘要
- 搜索结果（若触发搜索）

## 当前不会进入模型上下文的数据

- 其他会话完整消息历史
- private 会话摘要
- archived 会话摘要
- deleted 会话摘要

## 未来扩展：Tool Layer（预留）

当前仓库里还没有正式的 tool calling 层。

这里需要明确：当前的 service 不等于 tool。

- service 是当前应用后端的业务实现层，直接服务于 API Router 和聊天主流程
- future tool 是面向模型可调用能力的薄包装层，目标是复用现有 service，而不是替代它们

未来如果进入 agent 化阶段，`Tool Layer` 预期会作为 service 之上的一层轻包装，负责把现有能力整理成更适合模型调用的输入输出形式。

设计原则：

1. tool 不重复实现业务逻辑
2. tool 优先调用 service，不直接操作数据库
3. 当前聊天主流程不依赖 tool 层
4. tool 层属于未来扩展，不是当前 MVP 范围

未来可能出现的 tool 示例：

- `search_web`
- `get_project_detail`
- `list_project_sessions`
- `get_session_summary`
- `move_session_to_project`
- `archive_session`

如果后续真的进入这一阶段，目录形态可能类似：

```text
backend/app/tools/
  base.py
  registry.py
  search_tool.py
  project_tool.py
  session_tool.py
  memory_tool.py
```

上面只是预留示意，不代表当前仓库已经有这些文件，也不代表当前实现已经切到 tool-first 架构。
