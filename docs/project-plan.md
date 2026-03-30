# Project Plan

## 总体目标

把当前以单会话为主的聊天 demo，逐步扩展成一个具备：

- 项目层组织能力
- 会话层可见性与生命周期管理
- 受控跨会话上下文检索
- 更清晰权限边界

的演示型系统。

## 阶段拆分

### 阶段 1

项目层 + 会话层权限的数据模型与管理 API

状态：已完成

交付内容：

- 新增 `Project` 模型
- 扩展 `ChatSession.project_id`
- 扩展 `ChatSession.status`
- 扩展 `ChatSession.is_private`
- 新增项目管理 API
- 新增会话管理 API
- 新增最小测试覆盖项目创建、挂项目、归档、软删除

### 阶段 2

两层权限规则接入聊天上下文解析

状态：已完成

交付内容：

- 在 `MemoryService` 中新增上下文解析能力
- 项目层 `scope_mode` 正式接入聊天上下文边界
- 会话层 `is_private` 作为更严格收紧规则生效
- `is_isolated` 项目边界接入跨会话摘要读取
- 聊天时仍优先读取当前会话最近消息
- 其他会话只读取摘要，不直接拼接完整消息
- `ChatResponse` 新增轻量调试字段：
  - `context_scope`
  - `related_summary_count`
- 新增权限规则测试：
  - private 不被同项目其他会话读到
  - isolated 项目内容不被项目外 global 会话读到
  - project_only 只读项目内可访问历史
  - global 只读允许访问历史
  - deleted 不进入上下文

本阶段已实现的规则：

- 项目层决定默认边界
- 会话层只能收紧，不能放宽
- `is_private=true` 的当前会话会退化为 `conversation_only`
- private 会话不会被其他会话读到
- deleted 会话永远不进入上下文
- archived 会话当前不纳入上下文检索
- isolated 项目边界不能被跨项目读取穿透

本阶段刻意不做：

- allowlist
- 向量库
- 跨会话原始消息大规模拼接
- 更复杂的排序、召回、打分策略

### 阶段 3

更细粒度的记忆治理与检索优化

计划内容：

- allowlist 或显式授权规则
- 更稳定的跨会话摘要排序
- 更清晰的全局会话定义
- 更适合展示的前端管理页

## 当前阶段结论

当前仓库已经完成“项目层默认边界 + 会话层更严格收紧”规则接入聊天上下文。

当前会进入模型上下文的数据：

- 当前会话最近消息
- 当前会话摘要
- 按权限规则筛出的其他会话摘要

当前不会进入模型上下文的数据：

- 其他会话的完整原始消息
- private 会话摘要（当前会话自己除外）
- deleted 会话
- archived 会话
- 被 isolated 边界挡住的项目外摘要
- allowlist 相关内容（尚未实现）
