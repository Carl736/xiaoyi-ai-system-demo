# 小奕 · 智能教学助手

> 基于用户上传教材的 AI 问答助手 —— 只回答你教材里的内容，且能溯源到页码。

## 📖 项目背景

大学生在学习过程中常遇到这些困扰：

- 教材内容多，翻书找概念效率低
- 直接用 ChatGPT 提问，答案往往是通用知识，不符合自己学校教材的表述
- 不同学校、不同专业教材不同，同一个概念的定义、符号、证明顺序可能完全不同

**小奕** 的目标是：让用户上传自己的 PDF 教材，系统只从这本教材里检索内容，结合大模型生成回答，并标注页码。**不瞎编，能溯源。**

## ✨ 核心特性

| 特性 | 说明 |
| :--- | :--- |
| 📚 知识库管理 | PDF 上传 → 解析 → 分块 → Embedding → FAISS 检索，全流程自动化 |
| 🔍 RAG 问答 | 基于教材内容生成答案，返回页码，支持相似度阈值过滤（0.7） |
| 🤖 Agent 决策 | 大模型自主判断是否调用工具（教材检索 / 计算器），而非固定流程 |
| 🧠 对话记忆 | PostgreSQL 保存聊天记录，自动注入最近 6 轮对话作为上下文 |
| 👤 用户系统 | 注册 / 登录 / JWT 认证，数据按 user_id 隔离 |
| 📄 文档管理 | 教材列表、详情、统计、软删除；chunk_id 与 FAISS vector_id 一一对应 |

## 🏗️ 系统架构

```
用户请求
    ↓
FastAPI（API 层）
  /api/users  /api/upload  /api/chat  /api/documents
    ↓
Service 层
  chat_service  pdf_service  document_service
  agent_service  textbook_tool  calculator_tool
    ↓
数据 / AI 层
  PostgreSQL    FAISS IndexIDMap    DeepSeek LLM
  Document      向量检索            对话生成
  DocumentChunk Conversation Memory
```

## 🛠️ 技术栈

| 分类 | 技术 |
| :--- | :--- |
| 后端框架 | Python 3.10+, FastAPI, Uvicorn |
| 数据库 | PostgreSQL, SQLAlchemy (async), asyncpg, Redis (基础) |
| AI / RAG | Sentence-Transformers (384维), FAISS (IndexIDMap), DeepSeek API |
| Agent | LLM Tool Calling, Tool Schema, Conversation Memory |
| 运维 | Linux, Git, Docker (基础) |

## 📁 项目结构

```
xiaoyi-ai-system-demo/
├── app/
│   ├── api/                    # 路由层
│   │   ├── chat.py             # 聊天接口 /api/chat/ask
│   │   ├── user.py             # 用户接口 /api/users
│   │   ├── pdf.py              # PDF 上传 /api/upload/pdf
│   │   └── document.py         # 文档管理 /api/documents
│   ├── service/                # 业务逻辑层
│   │   ├── chat_service.py     # RAG 问答核心
│   │   ├── pdf_service.py      # PDF 解析 + 分块 + Embedding
│   │   ├── document_service.py # 文档管理
│   │   ├── agent_service.py    # Agent 决策
│   │   ├── textbook_tool.py    # 教材检索工具
│   │   ├── calculator_tool.py  # 计算器工具
│   │   └── memory_service.py   # 对话记忆
│   ├── model/                  # 数据库模型
│   │   ├── user.py
│   │   ├── chat_history.py
│   │   └── document.py
│   ├── schemas/                # Pydantic 模式
│   ├── vectorstore/            # FAISS 向量存储
│   │   └── faiss_db.py
│   ├── utils/                  # 工具函数
│   │   ├── chunking.py
│   │   └── embedding.py
│   ├── db/                     # 数据库连接
│   │   └── database.py
│   └── main.py                 # 入口
├── tests/                      # 测试脚本
│   ├── test_agent.py
│   └── test_tool_calling.py
├── requirements.txt
├── .gitignore
└── README.md
```

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/Carl736/xiaoyi-ai-system-demo.git
cd xiaoyi-ai-system-demo
```

### 2. 创建虚拟环境

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Mac/Linux
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

在项目根目录创建 `.env` 文件，填入以下内容：

```env
DEEPSEEK_API_KEY=你的DeepSeek密钥
DATABASE_URL=postgresql+asyncpg://用户名:密码@localhost:5432/xiaoyi_ai
```

### 5. 初始化数据库

```bash
python -m app.db.init_db
```

### 6. 启动服务

```bash
uvicorn app.main:app --reload
```

访问 `http://127.0.0.1:8000/docs` 查看 Swagger 文档。

## 📡 API 概览

| 方法 | 路径 | 说明 |
| :--- | :--- | :--- |
| POST | `/api/users/register` | 用户注册 |
| POST | `/api/users/login` | 用户登录 |
| POST | `/api/upload/pdf` | 上传 PDF 教材 |
| POST | `/api/chat/ask` | 提问（RAG + Agent） |
| GET | `/api/chat/history` | 获取聊天记录 |
| GET | `/api/documents` | 获取教材列表 |
| GET | `/api/documents/{id}` | 获取教材详情 |
| GET | `/api/documents/stats/overview` | 统计教材数 / Chunk 数 |
| DELETE | `/api/documents/{id}` | 软删除教材 |

## 💡 技术亮点

- **相似度阈值过滤**：低于 0.7 的检索结果不送入 LLM，有效减少幻觉。
- **user_id 数据隔离**：FAISS 检索时过滤 metadata，保证用户只能搜到自己的教材。
- **chunk_id 与 FAISS vector_id 一一对应**：PostgreSQL 管理业务数据，FAISS 负责向量检索，双向可追溯。
- **Agent 决策层**：通过 Prompt Engineering 让 DeepSeek 自主判断"是否需要搜教材"，而非固定流程。
- **异步全链路**：FastAPI + asyncpg + SQLAlchemy async，PDF 解析放入线程池避免阻塞事件循环。
- **软删除设计**：删除教材时标记 status=DELETED，检索时自动过滤，避免物理删除破坏索引。

## 🧪 测试

```bash
# 测试 Agent 决策准确率
python -m app.test_agent

# 测试 Tool Calling
python -m app.test_tool_calling
```

## 📌 后续规划

- [ ] 接入 Redis 缓存高频问答，降低 LLM 调用成本
- [ ] 支持多教材选择（按 document_id 限定检索范围）
- [ ] 实现 SSE 流式输出，提升用户体验
- [ ] Docker 容器化部署
- [ ] 完善 RAG 评测体系（Top-K 命中率、回答准确率）

## 📄 License

本项目基于 MIT 协议开源，详见 LICENSE。

---

> **小奕** —— 让每个学生都拥有一个懂自己教材的 AI 助教。
