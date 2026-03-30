# API 说明

## 概述

当前后端公开的主要接口有两个：

- `GET /health`
- `POST /api/chat`

接口目标是服务当前 demo 页面和本地联调，不是面向复杂第三方集成场景设计的完整开放 API。

## GET /health

### 作用

用于检查后端服务是否启动，以及当前运行环境是什么。

### 请求

```http
GET /health
```

### 成功响应示例

```json
{
  "status": "healthy",
  "environment": "development"
}
```

### 字段说明

- `status`
  服务状态。当前正常情况下固定返回 `healthy`。
- `environment`
  当前运行环境，来自后端配置。

## POST /api/chat

### 作用

接收一轮用户消息，完成上下文组织、搜索、模型调用和记忆落库，然后返回本轮回复。

### 请求

```http
POST /api/chat
Content-Type: application/json
```

### 请求体字段说明

```json
{
  "message": "你好，请记住我叫小王",
  "session_id": "optional-session-id"
}
```

- `message`
  用户当前输入的消息。
  - 类型：`string`
  - 必填：是
  - 限制：1 到 4000 个字符

- `session_id`
  会话标识。
  - 类型：`string`
  - 必填：否
  - 限制：最长 64 个字符
  - 说明：
    - 首次请求可以不传
    - 不传时后端会创建新的会话
    - 多轮对话时应复用后端第一次返回的 `session_id`

### 成功响应示例

```json
{
  "session_id": "8d4e5c7c5e954a5fa9f6d8f7567dc001",
  "reply": "你好，我会在当前会话里继续记住你提供的信息。",
  "summary": null,
  "used_live_model": true,
  "fallback_reason": null,
  "search_triggered": false,
  "search_used": false,
  "sources": []
}
```

### 响应字段说明

- `session_id`
  当前会话 ID。首次请求时由后端生成，后续请求应复用它。

- `reply`
  本轮助手回复内容。

- `summary`
  当前会话摘要。
  - 当消息轮数还不多时，可能为 `null`
  - 当会话变长后，后端会开始返回压缩后的摘要

- `used_live_model`
  是否成功使用了真实在线模型。
  - `true`：本次回复来自真实模型
  - `false`：本次回复走了本地降级逻辑

- `fallback_reason`
  降级原因。
  - 如果本次使用了真实模型，通常为 `null`
  - 如果走了降级逻辑，会返回简要原因，例如：
    - `missing_api_key`
    - `provider_request_failed:...`

- `search_triggered`
  是否命中了搜索触发逻辑。

- `search_used`
  是否真的拿到了搜索结果并参与返回。
  - `true`：通常表示 `sources` 非空
  - `false`：可能是未触发搜索，也可能是触发了但没有取到结果

- `sources`
  搜索来源列表。

## sources 结构说明

`sources` 是一个数组，每一项结构如下：

```json
{
  "title": "Example News",
  "url": "https://example.com/news",
  "snippet": "Example snippet."
}
```

字段含义：

- `title`
  来源标题
- `url`
  来源链接
- `snippet`
  来源摘要，可为空

## 错误响应示例

当前错误响应统一为：

```json
{
  "error": {
    "code": "validation_error",
    "message": "请求参数校验失败。"
  }
}
```

常见错误类型包括：

- `validation_error`
  请求结构不合法，例如缺少 `message`

- `http_error`
  路由层抛出的 HTTP 错误

- `internal_error`
  服务端处理过程中出现未预期异常

### 422 示例

```json
{
  "error": {
    "code": "validation_error",
    "message": "请求参数校验失败。"
  }
}
```

### 500 示例

```json
{
  "error": {
    "code": "http_error",
    "message": "聊天服务暂时不可用，请稍后重试。"
  }
}
```

## 使用建议

### 1. 首次请求

首次请求不要传 `session_id`，让后端自动创建。

示例：

```json
{
  "message": "你好，请记住我叫小王"
}
```

### 2. 复用 session

后续请求复用上一次返回的 `session_id`，否则后端会把它当作新会话。

示例：

```json
{
  "message": "我刚才告诉了你什么？",
  "session_id": "8d4e5c7c5e954a5fa9f6d8f7567dc001"
}
```

### 3. 实时问题触发搜索

如果问题中包含实时性较强的表达，更容易触发搜索逻辑，例如：

- 今天
- 最新
- 当前
- 新闻
- 价格
- 最近
- `today`
- `latest`
- `news`

示例：

```json
{
  "message": "today latest ai news",
  "session_id": "8d4e5c7c5e954a5fa9f6d8f7567dc001"
}
```

需要注意：

- `search_triggered = true` 不代表一定拿到了结果
- 如果当前网络不可用，可能会触发搜索但 `search_used = false`

### 4. 如何判断这次回复是否可信到“实时信息”

可以结合这几个字段一起看：

- `used_live_model`
- `search_triggered`
- `search_used`
- `sources`

如果：

- `used_live_model = true`
- `search_used = true`
- `sources` 非空

说明这次返回更接近“真实模型 + 搜索增强”的路径。

如果：

- `used_live_model = false`

说明本次走了降级回复，适合用来调试链路，不应把它当作正式实时回答。
