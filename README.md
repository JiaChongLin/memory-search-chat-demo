# memory-search-chat-demo

一个面向学习与展示的最小可运行 Web 聊天应用 Demo，目标是围绕“多轮对话 + 基础记忆 + 联网搜索”搭建一条尽量清晰、容易理解的实现路径。

这个仓库当前更偏应用实现，而不是通用 Agent 平台、工作流编排框架或 SDK。README 以“当前版本、设计目标、计划支持”为主，尽量真实反映项目状态，不夸大能力。

## 1. 项目简介

`memory-search-chat-demo` 希望提供一个足够小、但结构完整的聊天应用示例：

- 前端提供一个简单的聊天界面
- 后端接收用户消息并调用模型服务
- 同一会话内保留聊天历史，支持多轮对话
- 在上下文中加入基础记忆能力
- 当问题涉及实时信息时，触发联网搜索，再结合搜索结果生成回答

它适合作为公开学习型仓库，用来展示一个带“记忆”和“搜索”的聊天系统最小实现思路。

## 2. 功能特性

### 当前版本

- 已完成一版基于 FastAPI 的后端基础骨架
- 后端当前已拆分为配置层、接口层、服务层、数据模型层，便于后续继续扩写
- 聊天接口已经具备最小闭环：可接收消息、按 `session` 组织上下文、维护简化摘要，并预留联网搜索与真实模型接入位置
- 前端联调、SQLite 持久化和真实搜索服务仍在继续补充

### 设计目标

- Web 端聊天界面：用户可以输入消息并看到模型回复
- Python 后端：负责处理聊天请求、组织上下文、调用模型与搜索服务
- 多轮对话：同一 `session` 内保留历史消息
- 基础记忆：
  - 短期记忆：保留最近几轮消息作为上下文
  - 长期记忆的简化版：对会话进行摘要，并在后续对话中复用
- 联网搜索：
  - 当问题涉及“今天、最新、当前、新闻、价格、最近”等实时信息时触发搜索
  - 搜索结果参与最终回答生成，而不是单独返回

### 计划支持

- 更稳定的会话存储
- 更清晰的搜索触发策略
- 更可控的摘要更新逻辑
- 更方便展示的前端界面

## 3. 项目目标与边界

### 项目目标

- 做一个最小但完整的聊天应用 Demo
- 展示聊天、记忆、搜索三部分如何协作
- 保持实现简单，便于学习、阅读和二次改造

### 项目边界

- 不是通用 Agent 平台
- 不提供复杂的多工具编排能力
- 不以插件生态、工作流系统或 SDK 形式为目标
- 不追求生产级高可用、高并发和复杂权限设计
- 不默认包含复杂的长期知识库、向量数据库或完整 RAG 方案

换句话说，这个项目更关注“一个小型聊天应用如何把基础记忆和实时搜索接进来”，而不是构建一个通用 Agent 基础设施。

## 4. 技术栈

以下是推荐技术栈，也是 README 所对应的设计方向：

| 层级 | 技术 | 说明 |
| --- | --- | --- |
| Backend | FastAPI | 提供聊天接口，组织会话、记忆和搜索流程 |
| Frontend | HTML / CSS / JavaScript | 保持前端简单，降低理解门槛 |
| Database | SQLite | 用于存储会话、消息、摘要等轻量数据 |
| LLM Service | 阿里云百炼（DashScope） | 当前优先对接百炼平台的大语言模型调用 |
| Search Service | 独立服务层 | 负责搜索触发、搜索请求与结果整理 |

整体上采用“接口层 + 服务层 + 存储层”的轻量分层设计，便于后续替换模型服务或搜索服务。

## 5. 项目结构

建议目录结构如下：

```text
memory-search-chat-demo/
|-- .env.example
|-- .gitignore
|-- backend/
|   `-- app/
|       |-- __init__.py
|       |-- main.py
|       |-- api/
|       |   |-- __init__.py
|       |   `-- chat.py
|       |-- core/
|       |   |-- __init__.py
|       |   `-- config.py
|       |-- db/
|       |   |-- __init__.py
|       |   `-- models.py
|       |-- schemas/
|       |   |-- __init__.py
|       |   `-- chat.py
|       `-- services/
|           |-- __init__.py
|           |-- chat_service.py
|           |-- llm_service.py
|           |-- memory_service.py
|           `-- search_service.py
|-- frontend/
|-- LICENSE
|-- README.md
`-- requirements.txt
```

说明：

- `backend/app/main.py`：FastAPI 应用入口，负责创建应用并挂载路由
- `backend/app/api/chat.py`：聊天接口定义
- `backend/app/core/config.py`：统一读取根目录 `.env` 配置
- `backend/app/schemas/chat.py`：聊天请求与响应的数据结构
- `backend/app/services/chat_service.py`：负责串联聊天主流程
- `backend/app/services/memory_service.py`：负责短期记忆与简化摘要
- `backend/app/services/search_service.py`：负责搜索触发判断与搜索接入边界
- `backend/app/services/llm_service.py`：负责百炼模型调用封装
- `backend/app/db/models.py`：SQLite 相关数据模型定义
- `frontend/`：前端目录已预留，当前版本还未补入页面文件
- `.env.example`：根目录环境变量模板，当前先放大语言模型相关配置
- `requirements.txt`：当前后端骨架所需的最小依赖列表

当前这一节展示的是仓库里的真实目录结构；后续随着前端和持久化模块补齐，再继续同步更新。

## 6. 核心处理流程

### 聊天流程

1. 前端发送用户消息到后端聊天接口
2. 后端根据 `session` 读取历史消息
3. 组装当前输入、最近几轮对话和已有摘要
4. 判断当前问题是否需要联网搜索
5. 如需搜索，则查询实时信息并整理结果
6. 将上下文与搜索结果一并交给模型生成回答
7. 保存本轮用户消息与模型回复
8. 在合适时机更新会话摘要

### 记忆流程

#### 短期记忆

- 保存最近几轮消息
- 主要用于维持当前对话连续性
- 目标是简单直接，避免上下文无限增长

#### 长期记忆的简化版

- 不做复杂的长期知识管理
- 采用“会话摘要”的方式压缩历史信息
- 摘要可在对话变长后参与后续回答生成

### 搜索流程

- 先对用户问题做简单判断
- 如果命中“今天、最新、当前、新闻、价格、最近”等实时性强的表达，则触发搜索
- 搜索结果经过整理后加入模型上下文
- 最终回答由模型综合用户问题、会话历史、摘要和搜索结果生成

这部分设计强调“搜索参与生成”，而不是把搜索结果原样拼接给用户。

## 7. 本地运行方式

当前仓库还在早期阶段，下面更适合作为推荐的本地运行方式。随着代码逐步补齐，实际命令可能会有小幅调整。

### 1. 克隆仓库

```bash
git clone https://github.com/<your-name>/memory-search-chat-demo.git
cd memory-search-chat-demo
```

### 2. 创建 Python 虚拟环境

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

### 3. 安装后端依赖

当前建议直接通过根目录 `requirements.txt` 安装后端依赖：

```bash
pip install -r requirements.txt
```

目前 `requirements.txt` 中包含的是后端骨架运行所需的最小依赖：

- `fastapi`
- `uvicorn`
- `pydantic`
- `sqlalchemy`

如果后续接入具体的模型服务 SDK、搜索 SDK 或数据库迁移工具，再按实际需要补充。

### 4. 配置根目录 `.env`

建议将项目运行时配置统一放在仓库根目录 `.env` 中。

先复制模板文件：

Windows PowerShell:

```bash
Copy-Item .env.example .env
```

macOS / Linux:

```bash
cp .env.example .env
```

当前版本的 `.env.example` 先只包含大语言模型相关配置，优先面向阿里云百炼平台，后续再逐步补充搜索、数据库和其他运行参数。

### 5. 启动后端

```bash
uvicorn backend.app.main:app --reload
```

默认情况下，后端可以运行在：

```text
http://127.0.0.1:8000
```

启动后可以优先检查这两个地址：

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

### 6. 启动前端

如果前端保持为纯静态页面，可以直接在 `frontend/` 目录下使用一个简单静态服务器：

```bash
cd frontend
python -m http.server 5500
```

然后在浏览器中访问：

```text
http://127.0.0.1:5500
```

### 7. 配置说明

当前建议通过根目录 `.env` 管理运行配置，并在后端统一读取。

目前已写入模板的配置项主要是大语言模型：

- `LLM_PROVIDER`：模型服务提供方，当前建议为 `dashscope`
- `LLM_API_KEY`：百炼平台 API Key
- `LLM_MODEL`：默认模型名称，例如 `qwen-plus`
- `LLM_BASE_URL`：模型服务基础地址，可按实际接入方式调整

建议在后端通过 `backend/app/core/config.py` 统一读取这些配置。

搜索服务、数据库路径、记忆窗口等参数可以等后续实现对应模块时再补充进 `.env`。

## 8. 后续计划

- 补充 SQLite 持久化与数据库初始化逻辑
- 完成前端聊天页面与接口联调
- 增加会话摘要更新逻辑
- 增加基于关键词或规则的搜索触发
- 抽离 LLM Service 与 Search Service，降低耦合
- 增加基础日志与错误处理
- 补充最小测试与示例截图

## 9. License

本项目采用 [MIT License](./LICENSE)。

---

如果你正在寻找一个“结构不复杂、便于理解、可以逐步扩展”的聊天应用示例，这个仓库会更适合作为起点，而不是一个已经封装完善的通用框架。
