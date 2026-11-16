# 小奕技术架构描述事实核对

## 1. 技术栈事实

代码中可以确认：

1. Python、FastAPI、Uvicorn。
2. PostgreSQL、SQLAlchemy async、asyncpg。
3. Sentence-Transformers 的本地 MiniLM Embedding 模型。
4. FAISS，当前索引为 IndexIDMap 包装 IndexFlatIP，向量维度为 384。
5. DeepSeek API，通过 OpenAI 兼容 AsyncOpenAI 客户端调用。

README 还列有 Redis，但当前业务代码没有实际 Redis 连接、读写或缓存逻辑。简历中不应把 Redis 写成已经使用的项目组件。

## 2. 分层架构事实

目录职责可以概括为：

1. API：接收请求、依赖注入、鉴权依赖、响应和 HTTP 异常。
2. Schema：Pydantic 请求和响应模型。
3. Service：用户、聊天、Agent、工具、PDF、文档和 Memory 业务编排。
4. Model：User、Document、DocumentChunk、ChatHistory 等 ORM 模型。
5. DB：PostgreSQL 异步 Engine、AsyncSession、Session 工厂和 Base。
6. VectorStore：FAISS 索引、metadata、搜索、过滤、保存、加载和删除。

## 3. Agent 模块事实

app/service/agent_service.py 实现了：

1. 读取用户最近 6 条聊天历史。
2. 拼接 system prompt、历史和当前问题。
3. 向 DeepSeek 传入工具 schema。
4. 流式接收 delta.content 和 delta.tool_calls。
5. 普通回答直接结束并返回 done。
6. 工具调用解析工具名和 JSON arguments。
7. 调用 execute_tool_resilient。
8. 把工具结果写回 messages，继续下一轮。
9. 通过 max_iteration 默认值 5 限制循环。
10. 超过上限后直接返回兜底 done，不再回传模型继续循环。

## 4. Tool 模块事实

当前工具包括：

1. textbook_search。
2. calculator。

工具由 agent_tool.py 注册、按工具名分发，并处理：

1. 参数解析错误。
2. 权限错误。
3. 普通工具异常。
4. TimeoutError、ConnectionError、OSError 的重试和退避。
5. 教材检索空结果的降级处理。

## 5. RAG 模块事实

PDF 链路是：

1. PyPDF2 解析 PDF。
2. 每页文本使用 chunk_size=700、overlap=100 切分，单位是字符。
3. MiniLM 生成 384 维 Embedding。
4. FAISS 使用 IndexIDMap(IndexFlatIP)。
5. 向量 L2 归一化后通过内积实现余弦相似度检索。
6. 检索支持 user_id、document_ids 和 threshold 过滤。
7. 默认 textbook_search 的 top_k 是 3。

## 6. Memory 模块事实

1. PostgreSQL 的 chat_history 表持久化 question、answer、user_id 和 created_at。
2. Agent 读取最近 6 条历史。
3. 历史由 memory_service 查询，再由 agent_service 拼入 messages。
4. API 层完成回答后通过 save_chat 保存本轮问答。
5. 当前没有找到摘要压缩或结构化长期记忆实现。

## 7. 权限和数据隔离事实

1. 请求使用 HTTP Bearer Token。
2. get_current_user 从 token 查询用户身份。
3. textbook_search 在传入 document_ids 时校验文档是否属于当前 user_id。
4. FAISS metadata 中保存 user_id 和 document_id。
5. search 根据 user_id 和 document_ids 过滤检索结果。
6. 文档删除会从 FAISS 删除向量和 metadata，并把 PostgreSQL 文档状态改为 DELETED。

## 8. 测试和评测事实

仓库有：

1. test_agent.py：普通聊天、Memory、calculator、教材工具场景。
2. test_memory.py：Memory 和教材检索场景。
3. test_tool_calling.py：Tool Calling 场景。
4. app/eval：固定测试集、Agent 批量跑分、人工判分、指标统计和检索诊断。

描述“完成核心链路测试”时，应理解为已有脚本和评测流程，不要说成已经有完整自动化测试平台或自动 Recall@K 评测。

## 9. 写作时需要收窄的地方

1. “Redis”改为未实际接入，除非描述的是依赖或后续规划。
2. “JWT”按当前仓库规则改成“基于 Bearer Token 的身份认证”或“基于 Token 的鉴权”。
3. “流式输出”只能描述服务层存在流式生成和事件聚合；不要写成已经核实的 SSE 接口，除非代码中有实际 SSE 路由。
4. “多教材选择”要区分已有 document_ids 过滤能力和 README 中的规划描述。
5. “稳定性控制”可以落到重试、退避、空结果降级、异常回喂和最大迭代次数，不要泛泛写成高可用。
6. “个性化知识检索”应具体说明 user_id 和 document_ids 过滤。

## 10. 你自己改写时的推荐顺序

1. 先写技术栈。
2. 再写 API / Schema / Service / Model / DB / VectorStore 分层。
3. 再写 Agent Loop 的输入、决策、工具执行、回喂和终止条件。
4. 再写 RAG 的 PDF、切分、Embedding、FAISS 和过滤。
5. 再写 Memory 的表、字段和最近 6 条历史。
6. 再写 Token 鉴权和 user_id 数据隔离。
7. 最后写已有测试脚本和 eval 指标。
