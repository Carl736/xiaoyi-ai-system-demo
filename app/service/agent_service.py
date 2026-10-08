from typing import Optional, List
import json

from openai import OpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.service.agent_tool import TOOLS, execute_tool
from app.service.memory_service import get_chat_history


client = OpenAI(
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

    max_iteration = 5

    for iteration in range(max_iteration):

        print(
            f"\n========== Agent 第 {iteration + 1} 轮 =========="
        )

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.7,
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

            return message.content

        # ======================================
        # 7. 保存 Assistant Tool Call Message
        # ======================================

        messages.append(message)

        # ======================================
        # 8. 执行 Tool
        # ======================================

        for tool_call in message.tool_calls:

            tool_name = tool_call.function.name

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

                tool_result = await execute_tool(
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

    return (
        "抱歉，处理这个问题时调用工具次数过多，"
        "请重新描述问题。"
    )