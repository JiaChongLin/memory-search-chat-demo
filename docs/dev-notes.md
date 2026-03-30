# Dev Notes

## 本阶段实现约定

### 1. 权限规则集中在 ContextResolver

当前聊天上下文访问边界集中放在 `ContextResolver`，而不是散落到 `ChatService` 或重新塞回 `MemoryService`。

当前职责划分：

- `ChatService`
  负责编排
- `ContextResolver`
  负责访问规则与上下文解析
- `MemoryService`
  负责 recent messages / summary / append_turn
- `LLMService`
  负责把解析后的上下文交给模型

### 2. 项目层决定跨项目边界，会话层决定是否可被读取

当前优先级是：

1. 当前会话始终先读自己的 recent messages 和 summary
2. 再看当前会话所属项目的 `access_mode`
3. 再判断候选会话自身是否 private
4. 最后过滤候选会话的 `status`

也就是说：

- 项目层负责“我能不能读外部 / 外部能不能读进来”
- 会话层负责“别人能不能读我”
- private 不会限制该会话自己读取别人

### 3. 当前只读取其他会话摘要

其他会话当前不会把完整原始消息拼进模型上下文，只会带入摘要。

这么做的原因：

- 保持 token 成本更可控
- 降低误把过多历史塞进 prompt 的风险
- 先把访问边界落稳，再做更复杂的召回策略

### 4. archived / deleted 当前直接排除

当前实现选择简单策略：

- archived 会话不纳入外部上下文
- deleted 会话永远不纳入外部上下文

这样能减少当前阶段的规则复杂度。

### 5. 无项目 shared 会话属于开放历史

当前实现明确支持：

- 无项目且 `is_private=false` 的会话，可以被开放上下文读取
- 无项目且 `is_private=true` 的会话，不能被其他会话读取

这意味着“无项目”不再自动等于“只读自己”。

### 6. 旧 SQLite 文件说明

如果本地 SQLite 来自旧版 `scope_mode / is_isolated` 模型，当前初始化逻辑会尽量补 `access_mode` 字段，并做一次轻量映射：

- 旧 `project_only` / `is_isolated=true` 会尽量映射为新的 `project_only`
- 其他旧项目默认尽量映射到 `open`

但这个映射不是严格无损迁移。
如果你要严格按新产品规则验证行为，建议删除旧本地 SQLite 文件后重新初始化。

### 7. allowlist 仍未实现

当前没有 allowlist，也没有显式授权列表。

因此本阶段的访问系统仍然是：

- 项目层跨项目边界
- 会话层 private 可见性
- 生命周期过滤

## 后续开发建议

如果继续推进下一阶段，建议优先检查：

- 是否要把 `is_private` 演进成更显式的 `visibility_mode`
- 是否要给上下文解析补“为什么这条摘要可读/不可读”的调试说明
- 是否要为 archived 引入低优先级而不是完全排除
- 是否要在现有 `ContextResolver` 上增加 allowlist 过滤
