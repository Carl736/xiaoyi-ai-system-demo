# 小奕项目分层与文件职责

## 1. 先记住整体分层

可以把项目按职责理解成：

1. 入口层：app/run.py、app/main.py。
2. API 路由层：app/api。
3. Schema 数据校验层：app/schemas。
4. Service 业务服务层：app/service。
5. Model 数据模型层：app/model。
6. 数据库基础设施层：app/db。
7. 向量检索基础设施层：app/vectorstore。
8. 模型和基础能力层：app/core、app/utils、app/config。
9. 评测层：app/eval。
10. 文件和持久化数据：app/data、app/static。

这不是严格的框架强制分层，而是根据当前目录和调用职责做的代码事实归类。

## 2. 入口层

### app/run.py

启动 Uvicorn 开发服务器。

它的职责是让 FastAPI 应用运行起来，不负责具体业务。

### app/main.py

创建 FastAPI 应用，注册路由，加载或检查向量库，配置静态文件等。

可以把它理解成应用组装入口。

## 3. API 路由层

目录：app/api

路由层负责：

1. 接收 HTTP 请求。
2. 使用 FastAPI 解析参数。
3. 使用 Depends 获取数据库会话和当前用户。
4. 调用 service 层。
5. 把 service 结果转换成 HTTP 响应。
6. 把错误转换成 HTTPException 和状态码。

### app/api/user.py

用户相关接口：

1. 注册。
2. 登录。
3. 获取用户信息。
4. 更新用户信息。
5. 修改密码。

### app/api/pdf.py

PDF 上传接口。

它接收 UploadFile，验证当前用户和数据库会话，然后调用 PDF 处理服务。

### app/api/document.py

文档接口：

1. 获取当前用户文档列表。
2. 获取文档统计。
3. 获取单个文档及其 chunks。
4. 删除文档。

### app/api/chat.py

聊天接口：

1. 接收问题。
2. 获取当前用户。
3. 获取数据库会话。
4. 调用聊天服务。
5. 保存问答记录。
6. 返回问题和答案。

## 4. Schema 数据校验层

目录：app/schemas

Schema 主要描述 HTTP 输入和输出的数据形状，不负责真正执行数据库或 Agent 业务。

### app/schemas/user_schema.py

包含用户注册、用户信息、更新信息、修改密码、登录响应等 Pydantic 模型。

它负责：

1. 校验请求字段。
2. 限制字段类型。
3. 组织接口返回结构。
4. 使用 model_validate 把 ORM 对象转换为响应模型。

### app/schemas/chat_schema.py

描述聊天问题等请求数据，例如问题文本和可选文档范围。

## 5. Service 业务服务层

目录：app/service

这是项目中最核心的业务编排层。路由层不直接完成复杂业务，而是把任务交给 service。

### app/service/user_service.py

用户业务：

1. 根据用户名查询用户。
2. 根据 token 查询用户。
3. 校验当前用户。
4. 注册用户。
5. 验证密码。
6. 更新用户信息和密码。

### app/service/chat_service.py

聊天业务：

1. 调用 collect_agent_stream。
2. 获取 Agent 的最终 done 结果。
3. 整理 answer、iterations_used、tool_calls 和 truncated。
4. 保存聊天记录。

### app/service/agent_service.py

Agent 主循环：

1. 读取最近历史。
2. 拼接 system prompt、历史和当前问题。
3. 调用 DeepSeek。
4. 接收流式 delta。
5. 判断是普通回答还是 tool_call。
6. 调用工具执行层。
7. 把工具结果追加到 messages。
8. 继续下一轮，最多 max_iteration。
9. 生成最终 done 或超轮次兜底结果。

### app/service/agent_tool.py

工具注册、分发和 resilient 执行：

1. 定义工具 schema。
2. 注册 textbook_search 和 calculator。
3. 根据工具名选择执行函数。
4. 对瞬时错误进行重试和退避。
5. 对教材空结果进行降级处理。

### app/service/textbook_tool.py

教材检索工具：

1. 检查 document_ids 是否属于当前用户。
2. 把问题转成 Embedding。
3. 调用 FAISS search。
4. 按用户和文档范围过滤。
5. 返回文本、页码、来源、文档 ID 和相似度。

### app/service/calculator_tool.py

计算器工具的具体执行逻辑。

### app/service/pdf_service.py

PDF 入库业务链：

1. 解析 PDF。
2. 提取页码和文本。
3. 清洗和切分文本。
4. 写入 Document 和 DocumentChunk。
5. 生成 Embedding。
6. 组装 FAISS metadata。
7. 写入 FAISS。
8. 保存索引。

### app/service/document_service.py

文档业务：

1. 查询用户文档。
2. 查询文档 chunks。
3. 更新 chunk 的 vector_id。
4. 执行文档软删除。
5. 删除 FAISS 向量和 metadata。
6. 把 PostgreSQL 文档状态改成 DELETED。

### app/service/memory_service.py

读取聊天历史，给 Agent 提供最近的上下文。

### app/service/vector_service.py

向量相关的服务辅助逻辑。当前项目的具体向量索引实现主要在 vectorstore/faiss_db.py。

## 6. Model 数据模型层

目录：app/model

Model 描述 PostgreSQL 中的表结构和表之间的关系，不是 HTTP 请求模型。

### app/model/user.py

定义 User 和 token 相关的数据表模型，包括用户 ID、用户名、密码、联系方式等字段，以及 token 记录。

### app/model/document.py

定义：

1. Document 文档主表。
2. DocumentChunk 文档分块表。
3. DocumentStatus 状态枚举。

DocumentChunk 中有 document_id、page、content 和 vector_id 等字段。

### app/model/chat_history.py

定义聊天历史表，包括 user_id、question、answer 和 created_at。

## 7. 数据库基础设施层

目录：app/db

### app/db/database.py

负责：

1. 配置 PostgreSQL 连接地址。
2. 创建异步 Engine。
3. 创建 AsyncSession 工厂。
4. 定义 ORM Base。
5. 通过 get_db 给请求提供数据库会话。

### app/db/init_db.py

负责数据库初始化相关操作。

数据库层提供的是通用数据库能力，具体用户、文档和聊天业务仍由 service 层组织。

## 8. 向量检索基础设施层

目录：app/vectorstore

### app/vectorstore/faiss_db.py

负责 FAISS 的具体实现：

1. 创建 IndexFlatIP 或 IndexFlatL2。
2. 使用 IndexIDMap 支持自定义 ID。
3. 归一化向量。
4. 添加向量和 metadata。
5. 相似度搜索。
6. user_id 和 document_ids 过滤。
7. threshold 过滤。
8. 保存和加载索引。
9. 删除向量和 metadata。

Service 层决定什么时候检索，vectorstore 层负责怎么检索。

## 9. 模型和基础能力层

### app/core/model_loader.py

加载本地 SentenceTransformer Embedding 模型。

当前模型是 paraphrase-multilingual-MiniLM-L12-v2。

### app/utils/embedding.py

提供：

1. 单文本 Embedding。
2. 批量 Embedding。

### app/utils/chunking.py

提供文本切分能力。

### app/utils/prompt_builder.py

提供 prompt 组织辅助能力。

### app/utils/pwd_security.py

提供密码安全处理相关能力。

### app/config/settings.py

读取和保存配置，例如 DeepSeek API key 等设置。

## 10. 评测层

目录：app/eval

它不是线上请求链路，而是离线评测和诊断：

1. test_set.json：测试题。
2. run_eval.py：批量跑 Agent。
3. score_eval.py：统计指标。
4. clear_history.py：清理评测历史。
5. diag_retrieval.py：诊断 FAISS。
6. diag_threshold.py：观察原始分数。
7. diag_threshold2.py：扫描阈值。

## 11. 数据文件和静态资源

### app/data/pdfs

保存上传的 PDF 文件。

### app/data/vectors

保存 FAISS 索引文件和 metadata 文件。

### app/static

静态资源目录。当前包含 .gitkeep，用于保证目录存在。

## 12. 三条主要调用链

### 聊天链

HTTP 请求
→ app/api/chat.py
→ app/service/chat_service.py
→ app/service/agent_service.py
→ app/service/agent_tool.py
→ textbook_tool 或 calculator_tool
→ FAISS 或计算逻辑
→ Agent 最终答案
→ 保存 chat_history
→ 路由响应

### PDF 入库链

HTTP 上传
→ app/api/pdf.py
→ app/service/pdf_service.py
→ PDF 解析和 chunking
→ app/model/document.py 对应的数据库表
→ app/utils/embedding.py
→ app/vectorstore/faiss_db.py
→ 保存 FAISS

### 文档删除链

HTTP DELETE
→ app/api/document.py
→ app/service/document_service.py
→ get_document_by_id 做用户隔离
→ 查询 chunks
→ FAISS 删除 vector_id
→ 保存 FAISS
→ Document.status 改为 DELETED

## 13. 面试时怎么概括分层

需要抓住职责，不必把每个目录都说成严格的框架层：

1. API 层负责 HTTP 参数、鉴权依赖和响应。
2. Schema 层负责请求和响应的数据校验。
3. Service 层负责编排用户、聊天、Agent、PDF 和文档业务。
4. Model 层描述 PostgreSQL 表结构和关系。
5. DB 层负责 PostgreSQL 连接、Session 和事务基础设施。
6. Vectorstore 层负责 FAISS 索引和向量检索。
7. Core、utils、config 提供模型加载、Embedding、切分、密码和配置等基础能力。
8. Eval 层负责离线评测，不属于线上请求主链。
