from typing import Optional, List
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.service.agent_tool import TOOLS, execute_tool_resilient
from app.service.memory_service import get_chat_history,get_user_memories,select_history_with_budget,summary_process,get_recent_summary,create_or_update_summary
from app.core.llm_client import client

logger = logging.getLogger(__name__)



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
    Agent 流式执行：LLM 调用开 stream=True，token 级 yield。

    yield 的事件（dict，前端按 type 分发渲染）：
    - {"type": "token", "content": "..."}
        最终答案的一个文本片段。工具调用轮的 content 通常为空，
        所以正常情况下只有回答轮会 yield token。
    - {"type": "tool_call", "tool": "textbook_search"}
        开始执行工具，前端可渲染"正在检索教材…"。
    - {"type": "done", "answer": "...", "iterations_used": N,
       "tool_calls": [...], "truncated": False}
        整轮结束，带完整答案和统计。
    """

    # ---- 获取历史并拼接 messages ----
    # （重复代码的权衡：抽成公共函数是大重构，先接受重复，
    #  注释标明，未来可抽成 _build_messages()。）
    history = await get_chat_history(
        user_id=user_id,
        db=db,
        limit=6,
    )
    memories=await get_user_memories(
        user_id=user_id,
        db=db,
        limit=20 #防止长期记忆无限膨胀
    )

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    #将长期记忆拼入上下文
    if memories:
        memory_text="\n".join(
            memory.content
            for memory in memories
        )
        logger.debug(
            "已加载用户长期记忆 user_id=%s memory_count=%d",
            user_id,
            len(memories),
        )
        messages.append(
            {
                "role":"system",
                "content":(
                    "以下是关于当前用户的长期记忆：\n"
                    +memory_text
                ),
            }
        )

    cut_history,save_history=select_history_with_budget(history=history)
    summary_record=None
    summary_read_failed=False
    try:
        async with db.begin_nested():
            summary_record=await get_recent_summary(user_id=user_id,db=db)
    except Exception:
        summary_read_failed=True
        summary_record=None
        logger.warning(
            "读取摘要失败 user_id=%s",
            user_id,
            exc_info=True
        )


    previous_summary=None
    covered_id=None
    cut_sum=[]
    if summary_record is None:
        for cut_his in cut_history:
            cut_sum.append(cut_his)

    elif summary_record is not None:
        previous_summary=summary_record.content#取出旧摘要
        covered_id=summary_record.covered_through_chat_id#取出覆盖id

        for cut_his in cut_history:
            if summary_record.covered_through_chat_id is None or cut_his.id>covered_id :
                cut_sum.append(cut_his)

    if cut_sum and not summary_read_failed:
        #该条件防止程序误把“读取摘要失败（见164行）”当做“用户还没摘要”
        logger.info(
            "开始生成短期摘要user_id=%s dropped_rounds=%d",
            user_id,
            len(cut_sum),
        )
        try:
            result=await summary_process(previous_summary,cut_sum)

            async with db.begin_nested():
                #在当期那数据库事务里开一个保存点（savepoint），给这次事务写入设一个局部回滚点
                #如果失败except接住异常，result改为pre。。。程序同样记录warning并记录旧摘要
                await create_or_update_summary(
                    user_id=user_id,
                    content=result,
                    covered_through_chat_id=max(cut.id for cut in cut_sum),
                    db=db
                )
        except Exception:
            logger.warning(
                "短期摘要失败，回退到旧摘要或纯截断 user_id=%s",
                user_id,
                exc_info=True,#把异常类型，错误信息和traceback一起写进日志
            )
            result=previous_summary
    else:
        result=previous_summary


    if result:
        messages.append(
            {
                "role":"system",
                "content":"以下是该用户的短期摘要\n"+result
            }
        )





    if cut_history:
        logger.info(
            "短期历史触发预算截断 user_id=%s budget_estimated_chars=%d kept_rounds=%d dropped_rounds=%d",
            user_id,
            3000,
            len(save_history),
            len(cut_history),
        )
    else:
        logger.debug(
            "短期历史未触发预算截断 user_id=%s kept_rounds=%d",
            user_id,
            len(save_history),
        )

    for item in save_history:
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

    seen_tool_calls=set()

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
            stream=True,#True的意思一个一个碎片返回
        )

        # ---- 拼凑本轮的完整响应 ----
        # 流式返回的是碎片（delta），要自己拼成完整 message。
        # 两种碎片：content（文本） 和 tool_calls（工具调用，
        # 按 index 分片到达，name/arguments 可能分好几个 chunk）。
        content_parts = []
        # tc_acc: {index: {"id":..., "name":..., "arguments": "..."}}
        tc_acc = {}#用于收集工具调用碎片

        async for chunk in stream:#读取每个流式chunk
            #chunk 是完整的响应包，delta 是"这一小包里新增的内容"。注意是新增——每个包只带增量，不带之前发过的。
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
                    #setdefault：如果字典存在就取出原字典，如果不存在就创建空字典
                    acc = tc_acc.setdefault(
                        tc_delta.index,
                        {"id": "", "name": "", "arguments": ""},
                    )
                    if tc_delta.id:#如果这次碎片带有工具调用id，就存下来
                        acc["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            acc["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            # arguments 是字符串碎片，要拼接，
                            # 不能覆盖（否则只剩最后一片）。
                            acc["arguments"] += tc_delta.function.arguments

        full_content = "".join(content_parts)#将之前的文本碎片拼成完整的字符串

        # ---- 本轮是工具轮还是回答轮？----
        if not tc_acc:#如果没有工具调用，那就是普通回答轮
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
        tool_calls_this_round = []#构造标准工具调用列表
        for idx in sorted(tc_acc.keys()):#按工具调用索引排序
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
            is_duplicate = False
            try:
                arguments = json.loads(
                    tc["function"]["arguments"] or "{}"
                )
                normalized_arguments=json.dumps(
                    arguments,
                    sort_keys=True,
                    ensure_ascii=False,
                )#把参数字典整理成固定顺序的字符串
                call_key=f"{tool_name}:{normalized_arguments}"
                if call_key in seen_tool_calls:
                    print(
                        f"[Tool Guard] 重复调用已拦截，"
                        f"tool={tool_name}"
                    )
                    is_duplicate = True
                    tool_result={
                        "success":False,
                        "error":"duplicate_tool_call",
                        "message":"该工具和参数已经被调用过，不要原样重复调用，可以使用之前的结果或修改参数",
                    }

            except json.JSONDecodeError:

                tool_result = {
                    "success": False,
                    "error": "invalid_tool_arguments",
                    "message": "工具参数不是合法 JSON。",
                }

            else:

                # 复用第一步的兜底 wrapper：重试→降级→明确失败。

                # 自己不再写一套 try/except。
                if not is_duplicate:
                    try:
                        seen_tool_calls.add(call_key)
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
                        print(f"[Tool Guard] 第{iteration+1}轮，工具 {tool_name} 被拒绝，原因：{e}")

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


async def collect_agent_stream(
    question: str,
    user_id: int,
    db: AsyncSession,
    document_ids: Optional[List[str]] = None,
    max_iteration: int = 5,
    temperature: float = 0.7,
):
    """消费 run_agent_stream，返回最终 done 事件。"""
    result = None

    async for event in run_agent_stream(
        question=question,
        user_id=user_id,
        db=db,
        document_ids=document_ids,
        max_iteration=max_iteration,
        temperature=temperature,
    ):
        if event.get("type") == "done":
            result = event

    if result is None:
        raise RuntimeError("Agent 流式执行未返回 done 事件")

    return {
        "answer": result["answer"],
        "iterations_used": result["iterations_used"],
        "tool_calls": result["tool_calls"],
        "truncated": result["truncated"],
    }
