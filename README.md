# 小奕 · 教材驱动的 AI 学习助手

小奕允许用户上传 PDF 教材，并围绕教材内容进行检索问答。项目包含用户与文档管理、混合检索、工具调用、对话记忆，以及一份独立开发中的 LangGraph Agent 实现。

## 功能概览

- **PDF 知识库**：解析 PDF 页面、切分文本、生成 Embedding，并将 chunk 与页码、用户和文档元数据关联。
- **混合检索**：FAISS 语义检索与 jieba 分词后的 BM25 关键词检索并行执行，使用 RRF 合并排序；检索按用户和可选文档范围过滤。
- **Agent 工具调用**：手写 Agent 支持教材检索和计算器工具；参数按工具 schema 校验，阻止未声明参数与 `bool` 冒充整数，并在一次问答内拦截相同调用。
- **检索兜底**：瞬时错误使用退避重试；教材检索为空时以更低阈值和更大的 `top_k` 再查一次。
- **对话记忆**：PostgreSQL 保存聊天历史和长期用户记忆。上下文最多注入最近 6 轮、最多 20 条长期记忆；历史另有约 3000 字符的估算预算，超出的旧轮次可压缩为持久化摘要。
- **用户与文档管理**：提供注册、登录、JWT 认证、文档管理，以及基于 `user_id` 的数据隔离。
- **日志与配置**：统一配置 Python logging；DeepSeek API key 从 `.env` 读取，不放在源码中。
- **LangGraph 原型**：`app/service/agent_graph.py` 将上下文组装、模型调用、工具执行和收尾组织为 StateGraph。它目前通过独立测试入口运行，聊天 API 仍使用手写 Agent；检索子图尚未实现。

## 架构

```text
FastAPI API
  ├─ 用户、PDF、文档、聊天路由
  └─ 当前聊天 API → chat_service → agent_service（手写 Agent）
                                      ├─ textbook_search
                                      │    ├─ FAISS 语义检索
                                      │    ├─ BM25 关键词检索
                                      │    └─ RRF 融合与空结果降级
                                      └─ calculator

LangGraph 独立原型
  assemble_context → call_model → execute_tools → 条件路由 / 收尾

PostgreSQL：用户、文档、chunks、聊天历史、长期记忆、短期摘要
```

## 技术栈

| 层次 | 技术 |
| --- | --- |
| API | Python、FastAPI、Uvicorn |
| 数据库 | PostgreSQL、SQLAlchemy Async、asyncpg |
| 模型 | DeepSeek API、OpenAI Python SDK |
| 检索 | Sentence Transformers、FAISS、rank_bm25、jieba、RRF |
| Agent 工作流 | 手写流式工具调用；独立 LangGraph 原型 |

## 本地运行

### 1. 安装依赖

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. 配置服务

在项目根目录创建 `.env`，设置 `DEEPSEEK_API_KEY`。数据库连接地址目前在 `app/db/database.py` 中配置，请按本地 PostgreSQL 环境调整。

### 3. 创建数据库表

```powershell
python -c "import asyncio; from app.db.init_db import init_db; asyncio.run(init_db())"
```

### 4. 启动服务

```powershell
uvicorn app.main:app --reload
```

启动时会尝试加载 `data/vectors/faiss_index` 下的 FAISS 索引与 metadata，并据此构建 BM25 索引。没有已有索引时，可启动后通过 PDF 上传流程添加教材。交互式 API 文档位于 `http://127.0.0.1:8000/docs`。

## 主要 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/users/register` | 注册用户 |
| POST | `/api/users/login` | 登录并获取认证信息 |
| POST | `/api/upload/pdf` | 上传并处理 PDF 教材 |
| POST | `/api/chat/ask` | 发起教材问答或计算请求 |
| GET | `/api/chat/history` | 获取聊天历史 |
| GET | `/api/documents` | 获取文档列表 |
| GET | `/api/documents/{id}` | 获取文档详情 |
| GET | `/api/documents/stats/overview` | 文档与 chunk 统计 |
| DELETE | `/api/documents/{id}` | 删除文档 |

## 目录结构

```text
app/
├── api/             # FastAPI 路由
├── config/          # 配置
├── core/            # LLM client 与日志配置
├── db/              # 数据库连接与初始化
├── eval/            # 检索诊断和评测脚本
├── model/           # SQLAlchemy 数据模型
├── service/         # Agent、聊天、记忆、PDF、检索和工具逻辑
├── vectorstore/     # FAISS、BM25 与 RRF
└── utils/           # chunking 与 embedding
```

用户上传的 PDF、FAISS 文件和运行时环境变量不包含在仓库中。请在本地配置数据库、`.env` 和教材数据后运行项目。
