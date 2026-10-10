from typing import Optional, List
import json

from openai import AsyncOpenAI

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.service.agent_tool import TOOLS, execute_tool_resilient
from app.service.memory_service import get_chat_history


client = AsyncOpenAI(
    api_key=settings.settings.deepseek_api_key,
    base_url="https://api.deepseek.com/v1"
)



SYSTEM_PROMPT = """
你是“小奕”，一个智能教学助手。

你可以使用以下工具：

1. textbook_search
用于搜索用户上传的教材知识库。

如果用户的问题涉及：
- 教材内容
- 教材知识点
- 教材例题
- 教材章节
- 按照教材的方法回答
- 用户明确要求根据教材、课本、书本回答

应优先使用 textbook_search。

2. calculator
用于进行精确数学计算。

如果用户要求进行数学计算，
应优先使用 calculator，
不要自己进行复杂计算。

## 工具调用铁律（必须遵守）

1. 只要问题涉及教材，你**必须**先调用 textbook_search 拿到检索结果，
   再组织回答。**禁止**在未调用工具的情况下回答教材问题，
   更**禁止**声称"我检索过了"而实际上没有调用工具——这是撒谎。

2. 只要用户要求数学计算，你**必须**先调用 calculator，
   即使你觉得自己能心算出答案。拿到计算结果后再回答。

3. 只有当问题既不涉及教材、也不涉及计算时，才可以直接回答。

如果问题不需要工具，可以直接回答。

回答教材问题时：

1. 优先依据 textbook_search 返回的教材内容回答。

2. 如果 textbook_search 返回了教材内容：
   - 可以引用这些内容进行回答
   - 尽可能指出对应教材名称和页码
   - 不要把教材没有出现的内容说成教材原文或教材结论

3. 如果教材内容不足：
   - 明确告诉用户教材检索结果不足
   - 可以使用通用知识补充
   - 明确区分“教材依据”和“补充说明”

4. 如果教材检索不到相关内容：
   - 明确告诉用户“当前上传教材中没有检索到相关内容”
   - 不要编造教材来源

5. 不要虚构教材页码、章节或书名。

回答计算问题时：
- 优先使用 calculator
- 根据 calculator 返回的结果回答
- 不要自行编造计算结果。

回答计算问题时：
- 优先使用 calculator
- 根据 calculator 返回的结果回答用户

你可以参考之前的对话上下文。

如果用户使用：
“它”
“这个”
“刚才那个”
“前面说的”
等指代，请结合历史对话判断用户具体指的是什么。
"""


async def run_agent(
    question: str,
    user_id: int,
    db: AsyncSession,
    document_ids: Optional[List[str]] = None,
    max_iteration: int = 5,
    # 新增：采样温度。eval 时跑四档对照（0.1/0.3/0.5/0.7），
    # 看哪档任务完成率最高，就把哪档写进代码。
    # 默认 0.7，保持现有线上行为不变。
    temperature: float = 0.7,
):
    """
    Agent 核心执行流程：

    用户问题
        ↓
    Conversation Memory
        ↓
    DeepSeek
        ↓
    Tool Calling
        ↓
    Tool 执行
        ↓
    Tool Result
        ↓
    DeepSeek
        ↓
    最终答案
    """

    # ==========================================
    # 1. 获取 Conversation Memory
    # ==========================================

    history = await get_chat_history(
        user_id=user_id,
        db=db,
        limit=6,
    )

    # ==========================================
    # 2. 构建 messages
    # ==========================================

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    # ==========================================
    # 3. 加入历史对话
    # ==========================================

    for item in history:
        messages.append(
            {
                "role": "user",
                "content": item.question,
            }
        )

        messages.append(
            {
                "role": "assistant",
                "content": item.answer,
            }
        )

    # ==========================================
    # 4. 加入当前问题
    # ==========================================

    messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    # ==========================================
    # 5. Agent Loop
    # ==========================================
    # 新增：执行统计。eval 时用这些数据画"轮数分布直方图"，
    # 回答"5 轮上限怎么定的"时拿真实数据说话。
    iterations_used = 0  # 实际消耗的轮数
    tool_calls_made = []  # 调过的工具名序列，如 ["textbook_search", "calculator"]
    truncated = False  # 是否被 max_iteration 截断（没答完就被迫停了）

    for iteration in range(max_iteration):
        # 輪数从 1 开始计数，方便人类阅读
        # （iteration 本身从 0 开始）
        iterations_used = iteration + 1

        print(
            f"\n========== Agent 第 {iteration + 1} 轮 =========="
        )

        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=temperature,
        )

        message = response.choices[0].message

        # ======================================
        # 6. 不需要 Tool
        # ======================================

        if not message.tool_calls:

            print(
                "\n========== Agent Final Answer =========="
            )

            print(message.content)

            # 返回值从纯字符串改为 dict：答案 + 执行统计。
            # chat_service.ask_question 会取出 answer，API 层无感。
            return {
                "answer": message.content,
                "iterations_used": iterations_used,
                "tool_calls": tool_calls_made,
                "truncated": False,  # 正常答完，没被截断
            }

        # ======================================
        # 7. 保存 Assistant Tool Call Message
        # ======================================

        messages.append(message)

        # ======================================
        # 8. 执行 Tool
        # ======================================

        for tool_call in message.tool_calls:

            tool_name = tool_call.function.name

            # 新增：记录本轮调了什么工具。
            # eval 统计"工具选择正确率"时用：
            # 比如计算题调了 calculator 算选对，调了 textbook_search 算选错。
            tool_calls_made.append(tool_name)
            try:
                arguments = json.loads(
                    tool_call.function.arguments
                )

            except json.JSONDecodeError:

                tool_result = {
                    "success": False,
                    "error": "invalid_tool_arguments",
                    "message": "工具参数不是合法 JSON。",
                }

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(
                            tool_result,
                            ensure_ascii=False,
                        ),
                    }
                )

                continue

            print(
                "\n========== Agent Tool Call =========="
            )

            print(
                "Tool：",
                tool_name,
            )

            print(
                "Arguments：",
                arguments,
            )

            # ==================================
            # 执行 Tool
            # ==================================

            try:

                tool_result = await execute_tool_resilient(

                    tool_name=tool_name,
                    arguments=arguments,
                    user_id=user_id,
                    db=db,
                    document_ids=document_ids,
                )

            except PermissionError as e:

                tool_result = {
                    "success": False,
                    "error": "permission_denied",
                    "message": str(e),
                }

            except ValueError as e:

                tool_result = {
                    "success": False,
                    "error": "invalid_argument",
                    "message": str(e),
                }

            except Exception as e:

                print(
                    "\n========== Tool Error =========="
                )

                print(e)

                tool_result = {
                    "success": False,
                    "error": "tool_execution_failed",
                    "message": "工具执行失败，请稍后重试。",
                }

            print(
                "\n========== Tool Result =========="
            )

            print(tool_result)

            # ==================================
            # 9. Tool Result 返回给 LLM
            # ==================================

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(
                        tool_result,
                        ensure_ascii=False,
                    ),
                }
            )

    # ==========================================
    # 10. 防止 Agent 无限循环
    # ==========================================

    truncated = True

    return {
        "answer": (
            "抱歉，处理这个问题时调用工具次数过多，"
            "请重新描述问题。"
        ),
        "iterations_used": iterations_used,
        "tool_calls": tool_calls_made,
        "truncated": truncated,
    }



# ============================================================
# Agent 流式执行（SSE 用）
# ============================================================

async def run_agent_stream(
    question: str,
    user_id: int,
    db: AsyncSession,
    document_ids: Optional[List[str]] = None,
    max_iteration: int = 5,
    temperature: float = 0.7,
):
    """
    Agent 流式执行：与 run_agent 同一套 Agent Loop，
    区别是 LLM 调用开 stream=True，token 级 yield。

    为什么不直接改造 run_agent？
    run_agent 已被 chat_service / 测试脚本 / run_eval.py 依赖
    （返回 dict），改它会引发 breaking change（第四步的教训）。
    新开一个 generator，老代码零影响。

    yield 的事件（dict，前端按 type 分发渲染）：
    - {"type": "token", "content": "..."}
        最终答案的一个文本片段。工具调用轮的 content 通常为空，
        所以正常情况下只有回答轮会 yield token。
    - {"type": "tool_call", "tool": "textbook_search"}
        开始执行工具，前端可渲染"正在检索教材…"。
    - {"type": "done", "answer": "...", "iterations_used": N,
       "tool_calls": [...], "truncated": False}
        整轮结束，带完整答案和统计（字段与 run_agent 的 dict 一致）。
    """

    # ---- 第 1~4 步与 run_agent 完全一致：取历史、拼 messages ----
    # （重复代码的权衡：抽成公共函数是大重构，先接受重复，
    #  注释标明，未来可抽成 _build_messages()。）
    history = await get_chat_history(
        user_id=user_id,
        db=db,
        limit=6,
    )

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]


    for item in history:
        messages.append(
            {
                "role": "user",
                "content": item.question,
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": item.answer,
            }
        )

    messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    iterations_used = 0
    tool_calls_made = []
    truncated = False

    for iteration in range(max_iteration):

        iterations_used = iteration + 1

        print(
            f"\n========== Agent 第 {iteration + 1} 轮（流式） =========="
        )

        # 流式调用：DeepSeek 一个 token 一个 token 地吐，
        # 不用等整句生成完。await 拿到的是一个异步迭代器，
        # 后面的 async for 逐个取 token。
        #await 在这里是"挂起等 DeepSeek 接通直播"，拿到手的 stream 是一个异步迭代器——可以理解为"直播信号源"，后面用 async for 一段段取。
        stream = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=temperature,
            stream=True,  # 与 run_agent 唯一的区别
        )

        # ---- 拼凑本轮的完整响应 ----
        # 流式返回的是碎片（delta），要自己拼成完整 message。
        # 两种碎片：content（文本） 和 tool_calls（工具调用，
        # 按 index 分片到达，name/arguments 可能分好几个 chunk）。
        content_parts = []
        # tc_acc: {index: {"id":..., "name":..., "arguments": "..."}}
        tc_acc = {}

        async for chunk in stream:
            #chunk 是直播的一个小包，delta 是"这一小包里新增的内容"。注意是新增——每个包只带增量，不带之前发过的。
            delta = chunk.choices[0].delta

            # 文本碎片：直接 yield 给前端，实现打字机效果。
            # 工具调用轮的 content 通常为空，所以这里一般不会误 yield。
            if delta.content:
                content_parts.append(delta.content)#① 存进 content_parts（最后要拼成完整答案）
                yield {
                    "type": "token",
                    "content": delta.content,#② 立刻 yield 给前端（打字机效果）。工具调用轮的 content 通常是空的，所以这里不会误发。
                }

            # 工具调用碎片：按 index 累积，不 yield，
            # 等拼完整了再执行。
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    acc = tc_acc.setdefault(
                        tc_delta.index,
                        {"id": "", "name": "", "arguments": ""},
                    )
                    if tc_delta.id:
                        acc["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            acc["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            # arguments 是字符串碎片，要拼接，
                            # 不能覆盖（否则只剩最后一片）。
                            acc["arguments"] += tc_delta.function.arguments

        full_content = "".join(content_parts)

        # ---- 本轮是工具轮还是回答轮？----
        if not tc_acc:
            # 回答轮：token 已经 yield 完了，发 done 收尾。
            yield {
                "type": "done",
                "answer": full_content,
                "iterations_used": iterations_used,
                "tool_calls": tool_calls_made,
                "truncated": False,
            }
            return

        # ---- 工具轮：把累积的分片转成标准 tool_call 格式 ----
        # 标准格式（与非流式一致）：
        # [{"id":..., "type":"function",
        #   "function":{"name":..., "arguments":...}}]
        # 只有转成这个格式，execute_tool_resilient 和
        # messages.append 才能复用，不用重写。
        tool_calls_this_round = []
        for idx in sorted(tc_acc.keys()):
            acc = tc_acc[idx]
            tool_calls_this_round.append(
                {
                    "id": acc["id"],
                    "type": "function",
                    "function": {
                        "name": acc["name"],
                        "arguments": acc["arguments"],
                    },
                }
            )

        # 把本轮 assistant 消息拼回去（dict 形式，API 接受），
        # 否则下一轮 LLM 不知道上一轮调了什么工具。
        messages.append(
            {
                "role": "assistant",
                "content": full_content or None,
                "tool_calls": tool_calls_this_round,
            }
        )

        for tc in tool_calls_this_round:
            tool_name = tc["function"]["name"]
            tool_call_id = tc["id"]
            tool_calls_made.append(tool_name)

            # 告诉前端：正在调工具（可渲染"正在检索教材…"）
            yield {
                "type": "tool_call",
                "tool": tool_name,
            }

            try:
                arguments = json.loads(
                    tc["function"]["arguments"] or "{}"
                )

            except json.JSONDecodeError:

                tool_result = {
                    "success": False,
                    "error": "invalid_tool_arguments",
                    "message": "工具参数不是合法 JSON。",
                }

            else:

                # 复用第一步的兜底 wrapper：重试→降级→明确失败。
                # 自己不再写一套 try/except。
                try:

                    tool_result = await execute_tool_resilient(
                        tool_name=tool_name,
                        arguments=arguments,
                        user_id=user_id,
                        db=db,
                        document_ids=document_ids,
                    )

                except PermissionError as e:

                    tool_result = {
                        "success": False,
                        "error": "permission_denied",
                        "message": str(e),
                    }

                except ValueError as e:

                    tool_result = {
                        "success": False,
                        "error": "invalid_argument",
                        "message": str(e),
                    }

                except Exception as e:

                    print(
                        "\n========== Tool Error =========="
                    )

                    print(e)

                    tool_result = {
                        "success": False,
                        "error": "tool_execution_failed",
                        "message": "工具执行失败，请稍后重试。",
                    }

            print(
                "\n========== Tool Result =========="
            )

            print(tool_result)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps(
                        tool_result,
                        ensure_ascii=False,
                    ),
                }
            )

    # ---- 被 max_iteration 截断 ----
    truncated = True

    yield {
        "type": "done",
        "answer": (
            "抱歉，处理这个问题时调用工具次数过多，"
            "请重新描述问题。"
        ),
        "iterations_used": iterations_used,
        "tool_calls": tool_calls_made,
        "truncated": truncated,
    }