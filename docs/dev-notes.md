# 开发说明

## 本地开发目标

本地开发阶段的目标不是搭建复杂环境，而是尽快确认下面几件事：

- 后端能否正常启动
- 前端能否连上后端
- 聊天接口是否能创建并复用会话
- 摘要是否会生成
- 搜索是否会触发
- 模型不可用时是否会走降级

如果这些点都能验证通过，当前 demo 就已经具备继续开发的基础。

## 本地启动步骤

### 1. 创建并激活虚拟环境

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制模板：

Windows PowerShell:

```bash
Copy-Item .env.example .env
```

macOS / Linux:

```bash
cp .env.example .env
```

根据需要填写：

- 数据库地址
- LLM 配置
- 搜索开关
- 记忆参数

### 4. 启动后端

```bash
uvicorn backend.app.main:app --reload
```

### 5. 启动前端

```bash
cd frontend
python -m http.server 5500
```

然后访问：

```text
http://127.0.0.1:5500
```

## 常用检查地址

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:5500`

建议顺序是：

1. 先看 `/health`
2. 再看 `/docs`
3. 最后打开前端页面联调

## 关键配置说明

当前关键配置集中在根目录 `.env`。

### 数据库

- `DATABASE_URL`
  当前默认使用本地 SQLite，例如：
  `sqlite:///./app.db`

### LLM

- `LLM_PROVIDER`
  当前主要面向 `dashscope`

- `LLM_API_KEY`
  模型调用所需的 API Key

- `LLM_MODEL`
  模型名，例如 `qwen-plus`

- `LLM_BASE_URL`
  模型服务基础地址

- `LLM_TIMEOUT_SECONDS`
  模型请求超时时间

- `LLM_FALLBACK_ENABLED`
  模型请求失败时是否允许降级

### 记忆

- `MEMORY_SHORT_WINDOW`
  最近保留多少条消息作为短期上下文

- `MEMORY_SUMMARY_ENABLED`
  是否启用摘要

- `MEMORY_SUMMARY_MAX_CHARS`
  摘要最大长度

### 搜索

- `SEARCH_ENABLED`
  是否启用搜索

- `SEARCH_PROVIDER`
  当前 demo 里主要是 `duckduckgo`

- `SEARCH_BASE_URL`
  搜索请求地址

- `SEARCH_TIMEOUT_SECONDS`
  搜索超时时间

- `SEARCH_MAX_RESULTS`
  搜索返回结果数量上限

## 调试建议

### 先确认后端是否真的起来了

如果前端无法发送消息，第一步不要先怀疑前端，先看：

- `/health` 是否正常
- 终端里是否有导入报错或依赖缺失

### 优先区分“接口失败”和“模型失败”

当前后端已经实现了模型失败降级。

所以如果：

- 接口返回 200
- 但 `used_live_model = false`

说明主链路没断，只是模型没有正常调用成功。

### 搜索问题优先看这几个字段

- `search_triggered`
- `search_used`
- `sources`

这几个字段比单看回复内容更适合判断搜索链路是否生效。

### 摘要问题不要只测一轮

摘要是在会话变长后才更容易出现的。

建议连续发送几条消息，例如：

1. `记住我叫小王`
2. `我住在上海`
3. `我喜欢羽毛球`
4. `我刚才告诉了你什么？`

这样更容易观察摘要和多轮上下文是否工作。

### Windows 环境注意编码和网络问题

当前项目在 Windows PowerShell 下可能遇到两类常见问题：

- 中文显示乱码
- 网络受限导致模型或搜索调用失败

这两类问题都不一定是业务代码本身错误，要先和后端返回字段一起判断。

## 测试方式

### 1. 后端自动化测试

```bash
pytest -q
```

当前测试主要覆盖：

- 聊天接口基本行为
- 会话复用
- 搜索结果结构
- 记忆摘要
- 模型失败降级

### 2. Swagger 手工测试

打开：

```text
http://127.0.0.1:8000/docs
```

重点测试：

- 不传 `session_id` 的首次请求
- 复用 `session_id` 的多轮请求
- 实时问题请求

### 3. 前端页面联调

打开：

```text
http://127.0.0.1:5500
```

可重点观察：

- 后端健康状态
- 会话 ID 是否生成
- 摘要是否出现
- 搜索来源是否显示
- 是否走了降级路径

## 当前实现限制

当前版本已可演示，但还有这些限制：

- 搜索解析是 demo 级实现，不保证长期稳定
- 搜索触发逻辑主要依赖关键词
- 摘要质量有限
- 当前没有单独的会话查询接口
- 数据库迁移机制还没有引入
- 当前更适合单机本地开发，而不是生产部署

## 建议开发顺序

如果继续开发，建议按下面顺序推进：

1. 先保证本地前后端联调稳定
2. 再补会话查询或调试接口
3. 再优化搜索触发和搜索结果质量
4. 再改进前端体验
5. 最后再考虑更强的抽象和可扩展性

这样做的原因是，这个项目首先是应用 demo，优先级应当始终围绕“演示主链路稳定可观察”，而不是过早做平台化设计。
