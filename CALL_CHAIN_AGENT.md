# Agent 提问完整调用链

以下链路从聊天接口 `POST /api/chat/ask` 开始，按当前仓库代码记录。每一步都写明文件、函数、输入和输出。

1. **HTTP 请求进入聊天路由**

   - 文件：`app/api/chat.py`
   - 函数：`ask`
   - 输入：请求体解析为 `Question` 对象，问题文本在 `question.text`，可选文档范围在 `question.document_ids`。
   - FastAPI 通过 `user: User = Depends(get_current_user)` 注入当前用户，通过 `db: AsyncSession = Depends(get_db)` 注入数据库会话。
   - 下一步传递：`question.text`、`user.id`、`question.document_ids` 和 `db` 传给 `app/service/chat_service.py::ask_question`。

2. **读取 Authorization 并校验用户身份**

   - 文件：`app/service/user_service.py`
   - 函数：`get_current_user`
   - 上一步传入：FastAPI `HTTPBearer` 解析出的 `HTTPAuthorizationCredentials` 和数据库会话 `db`。
   - 处理：读取 `credentials.credentials` 作为 token；token 为空时抛出 HTTP 401。随后把 token 和 `db` 传给 `get_user_by_token`。
   - `get_user_by_token` 按 `UserToken.token` 查询 `user_token` 表；token 不存在或 `expires_at < datetime.now()` 时返回 `None`，否则按 `do_token.user_id` 查询 `User`。
   - 下一步传递：校验成功后返回 `User` 对象，`ask` 使用其中的 `user.id`。无效或过期 token 时抛 HTTP 401，详情为“无效令牌，可能已过期”。

3. **聊天服务接收问题**

   - 文件：`app/service/chat_service.py`
   - 函数：`ask_question`
   - 上一步传入：`question: str`、`db`、`user_id`、可选 `document_ids`。
   - 处理：调用 `collect_agent_stream`，把这四项继续传下去。
   - 下一步传递：`collect_agent_stream` 收到 Agent 的最终结果后，取出 `result["answer"]`，返回字符串给 `app/api/chat.py::ask`。

4. **消费流式 Agent 的最终事件**

   - 文件：`app/service/agent_service.py`
   - 函数：`collect_agent_stream`
   - 上一步传入：问题、用户 ID、数据库会话、文档 ID 列表，以及默认的最大轮数 5 和温度 0.7。
   - 处理：使用 `async for event in run_agent_stream(...)` 消费流式事件；中间的 `token` 和 `tool_call` 事件不作为最终返回，只保存最后的 `done` 事件。
   - 下一步传递：返回包含 `answer`、`iterations_used`、`tool_calls`、`truncated` 的字典给 `chat_service.ask_question`。

5. **Agent 读取历史并构造上下文**

   - 文件：`app/service/agent_service.py`、`app/service/memory_service.py`
   - 函数：`run_agent_stream`、`get_chat_history`
   - 上一步传入：`user_id` 和 `db` 传给 `get_chat_history`，并固定使用 `limit=6`。
   - `get_chat_history` 查询 `chat_history` 表中属于该用户的记录，按 `created_at.desc()` 取最近 6 条，再用 `list(reversed(history))` 恢复时间顺序。
   - 每条历史记录的 `question` 变成 `role="user"` 消息，`answer` 变成 `role="assistant"` 消息。
   - 上下文初始内容：先放 `SYSTEM_PROMPT`，再放最多 6 轮历史，最后放当前问题 `question`。

6. **进入 Agent 最大轮次循环**

   - 文件：`app/service/agent_service.py`
   - 函数：`run_agent_stream`
   - 输入：已经构造好的 `messages`，以及 `TOOLS`、`max_iteration=5`、`temperature=0.7`。
   - 循环：`for iteration in range(max_iteration)`，每一轮调用一次模型。`iterations_used` 记录当前轮数，`tool_calls_made` 记录工具名称。
   - 下一步传递：每轮把当前完整 `messages`、工具定义和运行参数传给 DeepSeek 客户端。

7. **以流式方式调用 DeepSeek**

   - 文件：`app/service/agent_service.py`
   - 函数：`run_agent_stream` 中的 `client.chat.completions.create`
   - 上一步传入：`model="deepseek-chat"`、`messages`、`tools=TOOLS`、`tool_choice="auto"`、`temperature`、`stream=True`。
   - 输出：`await` 得到一个异步数据流 `stream`，随后用 `async for chunk in stream` 逐个读取响应包。
   - 每个包的新增内容是 `chunk.choices[0].delta`，普通文本在 `delta.content`，工具调用碎片在 `delta.tool_calls`。

8. **处理普通文本增量**

   - 文件：`app/service/agent_service.py`
   - 函数：`run_agent_stream` 的 `async for chunk in stream` 循环。
   - 上一步传入：模型返回的 `delta.content` 文本碎片。
   - 处理：把每段文本追加到 `content_parts`，同时 `yield {"type": "token", "content": delta.content}`。
   - 下一步传递：调用方可以立即收到 `token` 事件；所有碎片读取完后，用 `"".join(content_parts)` 组成 `full_content`。

9. **判断本轮是最终回答还是工具调用**

   - 文件：`app/service/agent_service.py`
   - 函数：`run_agent_stream`
   - 判断：如果 `tc_acc` 为空，说明模型本轮没有发出工具调用。
   - 普通回答路径：发送 `type="done"` 事件，携带 `full_content`、迭代轮数、工具列表和 `truncated=False`，然后 `return` 结束整个 Agent。
   - 工具路径：如果 `tc_acc` 不为空，继续整理工具调用，不结束 Agent 循环。

10. **拼接工具调用碎片**

   - 文件：`app/service/agent_service.py`
   - 函数：`run_agent_stream` 中的 `tc_acc` 处理逻辑。
   - 上一步传入：每个 `delta.tool_calls` 中的工具调用碎片。
   - 处理：以 `tc_delta.index` 作为键，用 `setdefault` 为每个工具调用建立 `{id, name, arguments}`；工具参数通过 `+=` 拼接，避免后续碎片覆盖前面内容。
   - 下一步传递：按 `sorted(tc_acc.keys())` 构造标准的 `tool_calls_this_round` 列表，字段包括调用 ID、函数名和完整参数字符串。

11. **把 Assistant 的工具调用写回上下文**

   - 文件：`app/service/agent_service.py`
   - 函数：`run_agent_stream`
   - 上一步传入：整理完成的 `tool_calls_this_round` 和本轮 `full_content`。
   - 处理：向 `messages` 追加 `role="assistant"` 消息，其中包含 `tool_calls`。
   - 作用：让下一轮模型知道上一轮 Assistant 发出了哪些工具调用。

12. **向调用方报告正在调用工具**

   - 文件：`app/service/agent_service.py`
   - 函数：`run_agent_stream`
   - 上一步传入：每个标准工具调用 `tc`。
   - 处理：取出 `tc["function"]["name"]` 和 `tc["id"]`，记录工具名到 `tool_calls_made`，并 `yield {"type": "tool_call", "tool": tool_name}`。
   - 下一步传递：外部调用方可据此显示“正在检索教材”或“正在计算”等状态；工具执行继续在 Agent 内部进行。

13. **解析工具参数 JSON**

   - 文件：`app/service/agent_service.py`
   - 函数：`run_agent_stream`
   - 上一步传入：`tc["function"]["arguments"]` 字符串。
   - 处理：调用 `json.loads` 转成 Python 字典；参数为空时使用 `{}`。如果不是合法 JSON，捕获 `json.JSONDecodeError`，生成 `invalid_tool_arguments` 错误结果，不执行工具。
   - 下一步传递：合法参数进入工具执行；非法参数直接进入工具结果回填步骤。

14. **分发并执行具体工具**

   - 文件：`app/service/agent_service.py`、`app/service/agent_tool.py`
   - 函数：`execute_tool_resilient` → `_execute_with_retry` → `execute_tool`
   - 上一步传入：`tool_name`、解析后的 `arguments`、`user_id`、`db`、`document_ids`。
   - `execute_tool` 按工具名分发：`textbook_search` 调用 `app/service/textbook_tool.py::textbook_search`；`calculator` 调用 `app/service/calculator_tool.py::calculator`。
   - `execute_tool_resilient` 对瞬时错误最多重试 2 次；教材检索返回空列表时还会把 `top_k` 翻倍并把阈值改为 `DEGRADED_THRESHOLD=0.15` 后重查。

15. **教材检索工具的下游链路**

   - 文件：`app/service/textbook_tool.py`、`app/vectorstore/faiss_db.py`
   - 函数：`textbook_search` → `get_embedding` → `vector_store.search`
   - 上一步传入：问题文本、用户 ID、数据库会话、文档范围、`top_k` 和阈值。
   - 有 `document_ids` 时，先调用 `get_user_documents_by_document_ids` 验证文档属于当前用户且未软删除；验证失败抛出 `PermissionError`。
   - 问题通过 `get_embedding` 转为向量，再传给 FAISS；`search` 按 metadata 中的 `user_id` 和 `document_id` 过滤结果。
   - 下一步传递：返回包含 `text`、`page`、`source`、`document_id`、`score` 的结果列表；空结果返回 `[]`。

16. **计算器工具的下游链路**

   - 文件：`app/service/calculator_tool.py`
   - 函数：`calculator`
   - 上一步传入：`arguments["expression"]`。
   - 处理：解析并计算表达式；成功时返回表达式和计算结果，异常时返回包含 `error` 的字典。
   - 下一步传递：结果回到 `run_agent_stream`，不直接结束 Agent。

17. **捕获工具异常并统一成结果**

   - 文件：`app/service/agent_service.py`
   - 函数：`run_agent_stream` 中执行 `execute_tool_resilient` 的 `try/except`。
   - `PermissionError` 转为 `permission_denied`；`ValueError` 转为 `invalid_argument`；其他 `Exception` 打印日志后转为 `tool_execution_failed`。
   - 上一步传入：工具执行过程中的返回值或异常。
   - 下一步传递：得到统一的 `tool_result` 字典，后续作为工具消息回填给模型。

18. **把工具结果放回 messages**

   - 文件：`app/service/agent_service.py`
   - 函数：`run_agent_stream`
   - 上一步传入：`tool_result` 和对应的 `tool_call_id`。
   - 处理：把结果用 `json.dumps(..., ensure_ascii=False)` 转成 JSON 字符串，追加一条 `role="tool"` 消息，并带上对应的 `tool_call_id`。
   - 下一步传递：外层 Agent 循环开始下一轮模型调用，模型可以根据工具结果生成答案、继续调用工具或处理错误。

19. **超过最大轮数时的兜底**

   - 文件：`app/service/agent_service.py`
   - 函数：`run_agent_stream`
   - 触发条件：`range(max_iteration)` 执行完仍未进入普通回答路径，默认就是 5 轮后仍没有最终回答。
   - 输出：发送 `type="done"` 事件，答案为“抱歉，处理这个问题时调用工具次数过多，请重新描述问题。”，并设置 `truncated=True`。
   - 下一步传递：`collect_agent_stream` 接收该 `done` 事件并返回给 `chat_service.ask_question`。

20. **把最终答案返回给聊天接口**

   - 文件：`app/service/chat_service.py`、`app/api/chat.py`
   - `chat_service.ask_question` 从 Agent 结果中取出 `result["answer"]`，返回答案字符串。
   - `app/api/chat.py::ask` 收到答案后调用 `chat_service.save_chat`，把 `user_id`、原问题和最终答案写入 `ChatHistory`，执行 `commit` 并刷新记录。
   - 最终 HTTP 响应：返回 `{"question": question.text, "answer": answer}`。

