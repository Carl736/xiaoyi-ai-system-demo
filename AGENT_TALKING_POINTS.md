# Agent 问答链讲解提纲

本文件按仓库 AGENTS.md 的要求，只提供编号提纲和挑错意见，不提供可直接背诵的完整讲稿。你可以据此用自己的话讲到约 3 分钟。

1. **一句定位**

   - 核心句意：小奕是能根据问题自行决定是否检索教材的 Agent，工具选择由模型做，执行轮数和安全边界由代码控制。
   - 需要说清：它不是固定的“每个问题都先查教材”的写死流程。

2. **进入 Agent 循环前：验票拿身份**

   - 请求先进入 `app/api/chat.py::ask`。
   - `Depends(get_current_user)` 读取请求中的 token，反查数据库中的 `UserToken`，拿到当前 `User`。
   - 后续把 `user.id` 作为可信的 `user_id` 传入问答链，用于聊天历史、文档权限和检索隔离。

3. **进入 Agent 循环前：拼接上下文**

   - `ask` 调用 `app/service/chat_service.py::ask_question`。
   - `ask_question` 调用 `collect_agent_stream`，它消费 `run_agent_stream` 的事件并提取最终 `done` 结果。
   - `run_agent_stream` 先读取当前用户最近 6 条 `ChatHistory` 记录。
   - 6 条数据库问答记录会展开成 12 条消息：6 条 `role="user"` 和 6 条 `role="assistant"`；再加上系统提示、当前问题和工具定义菜单。
   - 这里要避免说成“6 轮 12 条历史问答”：准确说法是“最近 6 条问答记录，拼成 12 条历史消息”。

4. **循环本体：每轮模型有两条路**

   - `for iteration in range(max_iteration)` 控制最多 5 次模型调用。
   - 每轮把当前 `messages`、工具菜单和当前上下文交给模型。
   - 模型自行选择：
     1. 返回普通内容，表示直接回答；
     2. 返回工具调用，表示需要教材检索或计算。
   - 选择权属于模型；最大轮数属于代码。这样既保留 Agent 的自主决策，也避免模型无限调用工具。

5. **流式分片只需要一句带过**

   - 服务器接收模型返回的 chunk，从 `chunk.choices[0].delta` 取本次新增内容。
   - 普通内容片段放进 `content_parts`，工具调用片段按工具索引累积；本服务由收集器聚合最终 `done` 结果，不展开前端打字机或前端流式展示。

6. **直答路径**

   - 如果本轮没有 `tool_calls`，说明模型决定直接回答。
   - 代码把已拼好的 `full_content` 放进 `type="done"` 事件，并带上迭代次数、工具调用记录和 `truncated=False`。
   - `collect_agent_stream` 取出这个 `done` 事件，`ask_question` 只返回其中的 `answer`。

7. **工具调用路径**

   - 如果本轮有工具调用，代码先把 Assistant 的工具调用消息追加到 `messages`。
   - 工具参数原本是流式拼出的 JSON 字符串，通过 `json.loads` 转成 Python 字典。
   - 再调用 `execute_tool_resilient`，它根据工具名分发到 `textbook_search` 或 `calculator`。
   - 工具返回结果后，代码追加一条 `role="tool"` 消息，带上对应的 `tool_call_id`，再进入下一轮模型调用。
   - 要讲清顺序：当前轮先执行工具，下一轮模型再读取工具结果；不是把工具调用留到下一轮才执行。

8. **为什么工具出错不直接往上抛**

   - 工具错误被整理成结构化结果，例如权限错误、非法参数或工具执行失败。
   - 结构化结果会作为 `role="tool"` 消息回喂给模型。
   - 这样模型知道“这次工具没有成功以及失败原因”，可以向用户解释、修正参数或结束回答；如果直接把异常抛到 HTTP 层，Agent 会提前中断，模型看不到工具失败的上下文。
   - 需要说得准确：不是所有底层异常都永远不抛。重试耗尽后的异常会到 `run_agent_stream` 的异常处理边界，被转换成工具错误结果。

9. **工具执行层的错误三路**

   - `TimeoutError`、`ConnectionError`、`OSError` 属于可重试的瞬时错误。
   - `MAX_RETRIES=2` 表示额外重试 2 次，加上第一次尝试，总共最多 3 次。
   - 退避等待是 1 秒、2 秒，因为退避基数为 1.0，按指数倍增。
   - `PermissionError` 转成 `permission_denied`；`ValueError` 转成 `invalid_argument`；其他普通异常转成 `tool_execution_failed`，都作为工具结果交给模型。

10. **教材检索为空时的降级**

   - 只有 `textbook_search` 正常返回空列表时，`execute_tool_resilient` 才进入降级重查。
   - 第二次查询把 `top_k` 翻倍，并把阈值设为 `DEGRADED_THRESHOLD=0.15`。
   - 降级后仍为空，就返回明确的空结果说明，让模型告诉用户当前教材中没有检索到相关内容。
   - 代码注释中的“阈值降到 0.5”与实际常量不一致，讲解时按实际执行值 0.15 说。
   - calculator 返回带 `error` 的字典时，会被整理成 `invalid_expression` 结果；它不是教材检索的降级路径。

11. **为什么工具选择由模型决定，但轮数由代码决定**

   - 工具选择由 `tool_choice="auto"` 和系统提示共同影响，模型可以根据问题判断是否需要教材或计算器。
   - 轮数由 `max_iteration` 控制，这是代码设置的资源和流程边界。
   - 这样分工的原因：模型适合做语义判断，代码适合做确定性的次数限制和错误兜底。

12. **收尾与五轮熔断**

   - 正常路径：模型某轮不再请求工具，发送 `done`，`truncated=False`。
   - 熔断路径：5 轮都没有得到最终回答，循环结束后发送 `done`，答案为“抱歉，处理这个问题时调用工具次数过多，请重新描述问题。”，并设置 `truncated=True`。
   - 这里不要说成“循环里 break 报错”：当前代码是 `for` 循环跑完后发送兜底 `done` 事件。

13. **答案与落库的分工**

   - `collect_agent_stream` 提取 `answer` 等最终执行信息。
   - `chat_service.ask_question` 返回答案字符串给 `app/api/chat.py::ask`。
   - `ask` 再调用 `chat_service.save_chat`，把当前用户的 `user_id`、原问题和最终答案写入 `chat_history`。
   - Agent 负责生成和返回答案；聊天路由负责把问答记录落库并组成 HTTP 响应。

## 你原稿需要修正的事实

1. “六轮十二条历史问答”应改成“最近 6 条问答记录，展开为 12 条历史消息”。
2. 普通回答不是“把 type 改成 done”，而是先产生若干 token 事件，最后额外产生一个 done 事件。
3. 工具调用不是直接把 tool_call 喂给下一轮；当前轮会先执行工具，再把 Assistant 工具调用消息和 Tool 结果消息都追加到 `messages`，下一轮模型读取这些消息。
4. 超过 5 轮后不是在循环中直接 `break` 抛错，而是循环结束后发送带 `truncated=True` 的兜底 done 事件。
5. 可重试错误总尝试次数是 3 次：首次 1 次，加额外重试 2 次；退避等待是 1 秒、2 秒。
6. 工具错误不是简单“全部吞掉”：代码把错误转换成结构化 tool result 回喂模型；重试耗尽后也会在 Agent 层转换为工具错误结果。
7. 教材空结果降级的实际阈值是 0.15，`top_k` 翻倍；不要采用代码注释里写错的 0.5。
