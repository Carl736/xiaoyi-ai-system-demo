# Agent 代码事实核对单

以下内容仅依据当前仓库代码记录；文件路径均相对于仓库根目录。

1. **Agent 循环**

   - 文件：app/service/agent_service.py
   - 主循环是 run_agent_stream 中的 for iteration in range(max_iteration)，默认 max_iteration=5。
   - 每轮调用 DeepSeek chat.completions.create，传入 tools=TOOLS、tool_choice="auto"。
   - 达到上限仍未出现无工具调用的回答轮时，返回的兜底原文是：“抱歉，处理这个问题时调用工具次数过多，请重新描述问题。”，并返回 truncated=True。
   - 达到上限时返回同一段兜底回复；collect_agent_stream 会消费其 done 事件并返回兼容原调用方的结果字段。

2. **工具层：定义、参数 schema、注册/分发、报错路径**

   - 文件：app/service/agent_tool.py
   - textbook_search 和 calculator 都定义在模块级 TOOLS 列表中，Agent 调用时通过 tools=TOOLS 注册给模型。
   - textbook_search 的 schema 参数是必填 question（string）和可选 top_k（integer，默认 3）；schema 没有声明 threshold 或 document_ids。
   - calculator 的 schema 参数是必填 expression（string）。
   - 分发入口是 execute_tool：tool_name 为 textbook_search 时调用 app/service/textbook_tool.py 的 textbook_search；为 calculator 时调用 app/service/calculator_tool.py 的 calculator；未知名称抛出 ValueError。
   - Agent 实际调用 execute_tool_resilient。app/service/agent_service.py 会捕获 PermissionError、ValueError 和其他异常，转换为 tool message 后追加回 messages，交给模型继续下一轮。
   - TimeoutError、ConnectionError、OSError 最多重试 2 次；计算器返回带 error 的结果时返回结构化错误。未找到工具异常直接转换为 HTTP 请求失败的 Agent 路径。

3. **对话记忆**

   - 文件：app/service/memory_service.py、app/service/agent_service.py
   - get_chat_history 按 user_id 查询 ChatHistory，按 created_at 降序排列并 limit(limit)；run_agent_stream 以 limit=6 调用，最多取最近 6 条。
   - 查询结果随后 list(reversed(history))，恢复从旧到新的顺序。每条记录拼成 user/question 和 assistant/answer 两条 message，再追加当前问题。
   - 数据表模型文件是 app/model/chat_history.py，表名 chat_history，字段为 id、user_id、question、answer、created_at。
   - 超出 6 条时由 SQL 的 limit(6) 截断；未找到按 token 数再次截断的代码。

4. **流式输出**

   - 文件：app/service/agent_service.py
   - 找到真正的流式函数 run_agent_stream：调用 DeepSeek 时设置 stream=True，用 async for 读取增量，并 yield token、tool_call、done 事件字典。
   - app/api/chat.py 的 /api/chat/ask 走 chat_service.ask_question；该函数通过 collect_agent_stream 消费 run_agent_stream 的 done 事件后返回完整答案。已检查代码中未找到将 token 事件直接接到 HTTP/SSE 响应的入口，也未找到 StreamingResponse 或 EventSourceResponse。
   - 因此流式 Agent 函数存在且被内部消费，但当前聊天 HTTP 接口仍返回完整 JSON，而不是逐 token 的 HTTP/SSE 响应。

5. **JWT 鉴权**

   - 文件：app/service/user_service.py、app/api/user.py、app/model/user.py
   - 代码没有 JWT 编解码。create_token 用 uuid.uuid4() 生成随机字符串，过期时间为当前时间加 7 天 2 小时，写入 user_token 表的 token 和 expires_at 字段。
   - 注册和登录接口通过 app/api/user.py 调用 create_token 签发 token。
   - get_user_by_token 按 token 查询；不存在或 expires_at 早于当前时间时返回 None，否则按 user_id 查询用户。
   - get_current_user 使用 HTTPBearer 读取 Authorization。token 为空时抛 HTTP 401，详情为“Token 为空”；无效或过期时抛 HTTP 401，详情为“无效令牌，可能已过期”。
   - 未找到 JWT token 签发或 JWT 解码校验实现。

6. **数据隔离**

   - 文件：app/api/chat.py、app/service/chat_service.py、app/service/agent_service.py、app/service/agent_tool.py、app/service/textbook_tool.py、app/vectorstore/faiss_db.py
   - 请求经 get_current_user 得到 user，chat.py 把 user.id 传给 chat_service.ask_question；随后传给 run_agent_stream、execute_tool_resilient、execute_tool 和 textbook_search。
   - 上传时 app/service/pdf_service.py 将 user_id 写入每条 FAISS metadata。metadata 包含 chunk_id、text、page、source、document_id、user_id。
   - app/vectorstore/faiss_db.py 的 search 建立 metadata_map；传入 user_id 时跳过 item.get("user_id") != user_id 的条目，传入 document_ids 时跳过 item.get("document_id") not in document_ids 的条目。
   - textbook_search 带 document_ids 时，还会通过 get_user_documents_by_document_ids 校验文档属于当前用户且未软删除；集合不一致时抛 PermissionError。

7. **直答路径与空检索处理**

   - 文件：app/service/agent_service.py
   - 每轮收到模型消息后，若 not message.tool_calls，直接取 message.content，返回 answer 并结束 Agent 循环。模型是否先调工具由 tool_choice="auto" 和 system prompt 决定。
   - 空检索时 app/service/textbook_tool.py 返回 []。execute_tool_resilient 对 textbook_search 空结果执行一次降级：top_k 翻倍，阈值设为 DEGRADED_THRESHOLD=0.15，再查一次。
   - 降级后仍为空时返回 success=True、degraded=True、results=[]，并附带提示：“已尝试放宽检索条件，教材中仍没有检索到相关内容。请明确告诉用户当前上传的教材中没有相关内容，不要编造教材来源。”
   - Agent 将该结构序列化成 tool message 追加到上下文，继续调用模型；未找到空检索后直接结束 HTTP 请求的 Agent 路径。

