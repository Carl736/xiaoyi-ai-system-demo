#把该文件想象成一张流程图的施工文件，最终放置四类东西
#State定义：数据说明书
#节点函数：真正干活的函数。组装上下文、调用模型、执行工具、收尾。他们读State,做完工作返回更新
#路由判断：判断下一步去哪，例如模型有没有请求工具、轮数是否到达上限
#图的连接和编译：把节点按边连接起来，形成可运行的流程



#!!!!!!!!
#Langgraph节点的作用是做一段工作并返回State更新
from typing import TypedDict,Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from operator import add
import json
from app.core.llm_client import client
from app.service.agent_tool import TOOLS, execute_tool_resilient
from app.service.memory_service import get_chat_history,get_user_memories,select_history_with_budget,summary_process,get_recent_summary,create_or_update_summary
import logging
from langgraph.graph import StateGraph,START,END
from langgraph.config import get_stream_writer
from langchain_core.runnables import RunnableConfig
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




#共享的数据，State类本质只是声明工作单上有那些栏位，不会自己查数据库，调用模型或决定流程
#节点执行工作函数，边负责决定节点间怎么走
class State(TypedDict):
    #输入
    question:str
    user_id:int
    document_ids:list[str]|None
    max_iteration:int
    temperature:float

    #图运行数据
    messages:Annotated[list[dict],add]#节点更新message的时候只返回新增加的消息，不重复交,里面交代类型和更新规则
    iterations_used:int
    pending_tool_calls:list[dict]#tc_acc整理得到的toll_calls_this_round
    tool_calls_made:list[str]
    seen_tool_calls:set[str]
    truncated:bool
    answer:str
    full_content:str



#上下文准备节点
async def assemble_context(
        state:State,
        config:RunnableConfig,
):
    # ---- 获取历史并拼接 messages ----
    # （重复代码的权衡：抽成公共函数是大重构，先接受重复，
    #  注释标明，未来可抽成 _build_messages()。）
    db=config["configurable"]["db"]
    history = await get_chat_history(
        user_id=state["user_id"],
        db=db,
        limit=6,
    )
    memories = await get_user_memories(
        user_id=state["user_id"],
        db=db,
        limit=20  # 防止长期记忆无限膨胀
    )

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    # 将长期记忆拼入上下文
    if memories:
        memory_text = "\n".join(
            memory.content
            for memory in memories
        )
        logger.debug(
            "已加载用户长期记忆 user_id=%s memory_count=%d",
            state["user_id"],
            len(memories),
        )
        messages.append(
            {
                "role": "system",
                "content": (
                        "以下是关于当前用户的长期记忆：\n"
                        + memory_text
                ),
            }
        )

    cut_history, save_history = select_history_with_budget(history=history)
    summary_record = None
    summary_read_failed = False
    try:
        async with db.begin_nested():
            summary_record = await get_recent_summary(user_id=state["user_id"], db=db)
    except Exception:
        summary_read_failed = True
        summary_record = None
        logger.warning(
            "读取摘要失败 user_id=%s",
            state["user_id"],
            exc_info=True
        )

    previous_summary = None
    covered_id = None
    cut_sum = []
    if summary_record is None:
        for cut_his in cut_history:
            cut_sum.append(cut_his)

    elif summary_record is not None:
        previous_summary = summary_record.content  # 取出旧摘要
        covered_id = summary_record.covered_through_chat_id  # 取出覆盖id

        for cut_his in cut_history:
            if summary_record.covered_through_chat_id is None or cut_his.id > covered_id:
                cut_sum.append(cut_his)

    if cut_sum and not summary_read_failed:
        # 该条件防止程序误把“读取摘要失败（见164行）”当做“用户还没摘要”
        logger.info(
            "开始生成短期摘要user_id=%s dropped_rounds=%d",
            state["user_id"],
            len(cut_sum),
        )
        try:
            result = await summary_process(previous_summary, cut_sum)

            async with db.begin_nested():
                # 在当期那数据库事务里开一个保存点（savepoint），给这次事务写入设一个局部回滚点
                # 如果失败except接住异常，result改为pre。。。程序同样记录warning并记录旧摘要
                await create_or_update_summary(
                    user_id=state["user_id"],
                    content=result,
                    covered_through_chat_id=max(cut.id for cut in cut_sum),
                    db=db
                )
        except Exception:
            logger.warning(
                "短期摘要失败，回退到旧摘要或纯截断 user_id=%s",
                state["user_id"],
                exc_info=True,  # 把异常类型，错误信息和traceback一起写进日志
            )
            result = previous_summary
    else:
        result = previous_summary

    if result:
        messages.append(
            {
                "role": "system",
                "content": "以下是该用户的短期摘要\n" + result
            }
        )

    if cut_history:
        logger.info(
            "短期历史触发预算截断 user_id=%s budget_estimated_chars=%d kept_rounds=%d dropped_rounds=%d",
            state["user_id"],
            3000,
            len(save_history),
            len(cut_history),
        )
    else:
        logger.debug(
            "短期历史未触发预算截断 user_id=%s kept_rounds=%d",
            state["user_id"],
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
            "content": state["question"],
        }
    )
    return {
        "messages":messages
    }

#模型节点:完成一轮模型调用，不负责整个Agent循环
#收集响应，把结果交回State
#State不被直接修改，通过返回字典更新
async def call_model(
        state:State
):
    my_stream_writer=get_stream_writer()
    iterations_used=state["iterations_used"]+1
    # 流式调用：DeepSeek 一个 token 一个 token 地吐，
    # 不用等整句生成完。await 拿到的是一个异步迭代器，
    # 后面的 async for 逐个取 token。
    # await 在这里是"挂起等 DeepSeek 接通直播"，拿到手的 stream 是一个异步迭代器——可以理解为"直播信号源"，后面用 async for 一段段取。
    stream = await client.chat.completions.create(
        model="deepseek-chat",
        messages=state["messages"],
        tools=TOOLS,
        tool_choice="auto",
        temperature=state["temperature"],
        stream=True,  # True的意思一个一个碎片返回
    )

    # ---- 拼凑本轮的完整响应 ----
    # 流式返回的是碎片（delta），要自己拼成完整 message。
    # 两种碎片：content（文本） 和 tool_calls（工具调用，
    # 按 index 分片到达，name/arguments 可能分好几个 chunk）。
    content_parts = []
    # tc_acc: {index: {"id":..., "name":..., "arguments": "..."}}
    tc_acc = {}  # 用于收集工具调用碎片

    async for chunk in stream:  # 读取每个流式chunk
        # chunk 是完整的响应包，delta 是"这一小包里新增的内容"。注意是新增——每个包只带增量，不带之前发过的。
        delta = chunk.choices[0].delta


        if delta.content:
            content_parts.append(delta.content)  # ① 存进 content_parts（最后要拼成完整答案）
            my_stream_writer({
                "type": "token",
                "content": delta.content,
            })


        # 等拼完整了再执行。
        if delta.tool_calls:
            for tc_delta in delta.tool_calls:
                # setdefault：如果字典存在就取出原字典，如果不存在就创建空字典
                acc = tc_acc.setdefault(
                    tc_delta.index,
                    {"id": "", "name": "", "arguments": ""},
                )
                if tc_delta.id:  # 如果这次碎片带有工具调用id，就存下来
                    acc["id"] = tc_delta.id
                if tc_delta.function:
                    if tc_delta.function.name:
                        acc["name"] = tc_delta.function.name
                    if tc_delta.function.arguments:
                        # arguments 是字符串碎片，要拼接，
                        # 不能覆盖（否则只剩最后一片）。
                        acc["arguments"] += tc_delta.function.arguments

    full_content = "".join(content_parts)  # 将之前的文本碎片拼成完整的字符串
    # ---- 本轮是工具轮还是回答轮？----
    if not tc_acc:  # 如果没有工具调用，那就是普通回答轮
        return{
            "answer":full_content,
            "pending_tool_calls":[],
            "iterations_used":iterations_used
        }

    # ---- 工具轮：把累积的分片转成标准 tool_call 格式 ----
    # 标准格式（与非流式一致）：
    # [{"id":..., "type":"function",
    #   "function":{"name":..., "arguments":...}}]
    # 只有转成这个格式，execute_tool_resilient 和
    # messages.append 才能复用，不用重写。
    tool_calls_this_round = []  # 构造标准工具调用列表
    for idx in sorted(tc_acc.keys()):  # 按工具调用索引排序
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

    return {
        "iterations_used":iterations_used,
        "pending_tool_calls":tool_calls_this_round,
        "full_content":full_content
    }


#工具节点，call_model只告诉图“模型想调用哪些工具”，
# 该节点才负责工具执行
async def execute_tools(
        state:State,
        config:RunnableConfig
):
    db=config["configurable"]["db"]
    iterations_used=state["iterations_used"]
    tool_calls_made=list(state["tool_calls_made"])
    seen_tool_calls=set(state["seen_tool_calls"])
    messages=[]
    my_stream_writer=get_stream_writer()
    # 把本轮 assistant 消息拼回去（dict 形式，API 接受），
    # 否则下一轮 LLM 不知道上一轮调了什么工具。

    tool_calls_this_round=state["pending_tool_calls"]
    messages.append(
        {
            "role": "assistant",
            "content": state["full_content"] or None,
            "tool_calls": tool_calls_this_round,
        }
    )

    for tc in tool_calls_this_round:
        tool_name = tc["function"]["name"]
        tool_call_id = tc["id"]
        tool_calls_made.append(tool_name)

        my_stream_writer({
            "type": "tool_call",
            "tool": tool_name,
        })

        is_duplicate = False
        try:
            arguments = json.loads(
                tc["function"]["arguments"] or "{}"
            )
            normalized_arguments = json.dumps(
                arguments,
                sort_keys=True,
                ensure_ascii=False,
            )  # 把参数字典整理成固定顺序的字符串
            call_key = f"{tool_name}:{normalized_arguments}"
            if call_key in seen_tool_calls:
                print(
                    f"[Tool Guard] 重复调用已拦截，"
                    f"tool={tool_name}"
                )
                is_duplicate = True
                tool_result = {
                    "success": False,
                    "error": "duplicate_tool_call",
                    "message": "该工具和参数已经被调用过，不要原样重复调用，可以使用之前的结果或修改参数",
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
                        user_id=state["user_id"],
                        db=db,
                        document_ids=state["document_ids"],
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
                    print(f"[Tool Guard] 第{iterations_used}轮，工具 {tool_name} 被拒绝，原因：{e}")

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
    return {
        "messages":messages,
        "tool_calls_made":tool_calls_made,
        "seen_tool_calls":seen_tool_calls
    }


#模型后的路由：
def route_after_model(
        state:State
)->str:
    if state["pending_tool_calls"]:
        return "execute_tools"

    return "finish_answer"

#工具后的路由

def route_after_tools(
        state:State,
)->str:
    if state["iterations_used"] >= state["max_iteration"]:
        return "finish_truncated"
    return "call_model"

#接收state，通过get_syream_writer发送一个done事件
async def finish_answer(
        state:State
):
    my_stream_writer=get_stream_writer()

    my_stream_writer(
        {
            "type":"done",
            "answer":state["answer"],
            "iterations_used":state["iterations_used"],
            "tool_calls":state["tool_calls_made"],
            "truncated":False
        }
    )

    return {}

#收尾节点
async def finish_truncated(
        state:State
):
    my_stream_writer=get_stream_writer()
    my_stream_writer(
        {
            "type":"done",
            "answer":(
                "抱歉，处理这个问题时调用工具次数过多，"
                "请重新描述问题。"
            ),
            "iterations_used":state["iterations_used"],
            "tool_calls":state["tool_calls_made"],
            "truncated":True
        }
    )
    return {
        "answer":(
                "抱歉，处理这个问题时调用工具次数过多，"
                "请重新描述问题。"
            ),
        "truncated":True
    }


#创建图的构造器
workflow=StateGraph(State)

#登记节点
workflow.add_node("assemble_context",assemble_context)
workflow.add_node("call_model",call_model)
workflow.add_node("execute_tools",execute_tools)
workflow.add_node("finish_answer", finish_answer)
workflow.add_node("finish_truncated", finish_truncated)

#连接固定边:这几条边都是固定的，其他边需要条件判断方向
workflow.add_edge(START,"assemble_context")
workflow.add_edge("assemble_context","call_model")
workflow.add_edge("finish_answer",END)
workflow.add_edge("finish_truncated",END)

#连接条件边：
workflow.add_conditional_edges(
    "call_model",
    route_after_model,
    {
        "execute_tools":"execute_tools",
        "finish_answer":"finish_answer",
    },
)

workflow.add_conditional_edges(
    "execute_tools",
    route_after_tools,
    {
        "call_model":"call_model",
        "finish_truncated":"finish_truncated",
    },
)

#根据配置生成真正可运行的图
compiled_graph=workflow.compile()

#生成图的调用方，要有人把问题，用户身份和数据库会话加进去并读取图发出的事件
async def run_graph_stream(
        question:str,
        user_id:int,
        db:AsyncSession,
        document_ids:list[str] | None=None,
):
    initial_state:State={
        "question":question,
        "user_id":user_id,
        "document_ids":document_ids,
        "max_iteration":5,
        "temperature":0.7,
        "messages":[],
        "iterations_used":0,
        "pending_tool_calls":[],
        "tool_calls_made": [],
        "seen_tool_calls": set(),
        "truncated": False,
        "answer": "",
        "full_content": "",
    }

    #用async for接收事件，节点通过get_writer_stream发出的事件会逐个传到这里
    async for event in compiled_graph.astream(
            initial_state,
            config={"configurable": {"db": db}},
            stream_mode="custom",
    ):
        yield event#把事件继续交给run_graph_stream的调用方


async def consume_graph_events(
        question:str,
        user_id:int,
        db:AsyncSession,
):
    async for event in run_graph_stream(question,user_id,db):
        if event.get("type")=="token":
            print(event.get("content"))

        elif event.get("type")=="tool_call":
            print(event.get("tool"))

        elif event.get("type")=="done":
            print(event.get("answer"))
