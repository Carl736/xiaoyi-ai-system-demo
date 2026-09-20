# app/service/agent_service.py
from typing import Dict
import json
from openai import OpenAI
from app.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from app.service.agent_tool import TOOLS,execute_tool
from app.service.memory_service import get_chat_history
client = OpenAI(
    api_key=settings.settings.deepseek_api_key,
    base_url="https://api.deepseek.com/v1"
)

async def run_agent(
        question:str,
        user_id:int,
        db:AsyncSession,
):
    """
        Agent 主循环：

        1. 把用户问题交给 LLM
        2. LLM 判断是否需要调用 Tool
        3. 如果需要 Tool，则执行 Tool
        4. 把 Tool Result 返回给 LLM
        5. LLM 生成最终回答
        """
    history= await get_chat_history(
        user_id=user_id,
        db=db,
        limit=6,
    )
    messages = [
        {
            "role": "system",
            "content": """
    你是“小奕”，一个智能教学助手。

    你可以使用以下工具：

    1. textbook_search
    用于搜索用户上传的教材。
    如果用户的问题涉及教材内容、教材知识点、教材例题、
    教材章节或者要求按照教材的方法回答，应优先使用这个工具。

    2. calculator
    用于进行精确数学计算。
    如果用户要求进行数学计算，应使用 calculator 工具，
    不要自己进行复杂计算。

    如果问题不需要工具，可以直接回答。

    回答教材问题时：
    - 优先依据教材搜索结果
    - 不要编造教材中不存在的信息
    - 如果教材搜索不到相关内容，要明确告诉用户
    - 可以结合通用知识进行补充，但要说明教材中没有找到

    回答计算问题时：
    - 优先使用 calculator
    - 根据 calculator 返回的结果回答用户。

    你可以参考之前的对话上下文。
    如果用户使用“它”“这个”“刚才那个”等指代，
    请结合历史对话判断用户具体指的是什么。
    """
        }
    ]

    # ======================================
    # 加入历史对话
    # ======================================

    for item in history:
        messages.append({
            "role": "user",
            "content": item.question,
        })

        messages.append({
            "role": "assistant",
            "content": item.answer,
        })

    # ======================================
    # 最后加入当前问题
    # ======================================

    messages.append({
        "role": "user",
        "content": question,
    })
    # ======================================
    # Agent 循环
    # ======================================
    max_iteration=5

    for iteration in range(max_iteration):
        print(
            f"\n========== Agent 第 {iteration + 1} 轮 =========="
        )

        response=client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=TOOLS,#告诉 DeepSeek：你现在可以使用这些工具。
            tool_choice="auto",#你自己决定是否需要Tool
            temperature=0.7
        )

        message=response.choices[0].message

        #没有调用Tool
        if not message.tool_calls:
            return message.content#如果不需要调用，直接返回

        #有tool调用
        messages.append(message)

        for tool_call in message.tool_calls:

            tool_name=tool_call.function.name

            arguments=json.loads(
                tool_call.function.arguments#DeepSeek 返回的 arguments 本质上通常是 JSON 字符串。'{"question":"泰勒公式","top_k":5}'
            )
            print("\n========== Agent Tool Call ==========")
            print("Tool：", tool_name)
            print("Arguments：", arguments)

            try:
                tool_result = await execute_tool(
                    tool_name=tool_name,
                    arguments=arguments,
                    user_id=user_id,
                    db=db,
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
                print("\n========== Tool Error ==========")
                print(e)

                tool_result = {
                    "success": False,
                    "error": "tool_execution_failed",
                    "message": "工具执行失败，请稍后重试。",
                }
            print("\n========== Tool Result ==========")
            print(tool_result)

            #把Tool的执行结果告诉LLM
            messages.append({
                "role":"tool",
                "tool_call_id":tool_call.id,
                "content":json.dumps(
                    tool_result,
                    ensure_ascii=False
                )
            })
    # ======================================
    # 防止 Agent 无限循环
    # ======================================

    return "抱歉，处理这个问题时调用工具次数过多，请重新描述问题。"
def should_search_textbook(question: str) -> dict:
    """
    让大模型判断：用户问题是否需要搜索教材。

    返回：
        {
            "need_search": True/False,
            "reason": "判断理由"
        }
    """

    prompt = f"""
你是一个智能路由助手。判断用户问题是否与"教材知识库"相关。

判断规则：
- 需要搜教材：用户问数学公式、定理证明、概念解释、教材章节、例题详解等
- 不需要搜教材：用户问天气、问候、个人情况、与学习无关的闲聊

用户问题：{question}

只回复 JSON，格式如下：
{{"need_search": true/false, "reason": "简短判断理由"}}
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        # 兜底：解析失败时默认搜教材
        return {
            "need_search": True,
            "reason": f"决策解析失败，默认搜教材：{e}"
        }

def route_question(question:str)->Dict:
    """
       Agent 路由器。

       根据用户问题决定下一步应该调用哪个 Tool。

       返回：

       {
           "tool": "textbook_search",
           "reason": "用户询问教材相关知识"
       }

       或：

       {
           "tool": "general_chat",
           "reason": "普通闲聊，不需要教材"
       }
       """
    prompt=f"""
你是“小奕”的智能路由Agent。
你的任务是分析用户问题，并决定应该调用哪个工具。
目前你有两个工具，
1.textbook_search
    用于搜索用户上传的教材知识库
    
    适用：
    -数学公式
    -数学定理
    -定理证明
    -概念解释
    -教材章节
    -教材例题
    -教材中的解题方法
    -教材知识点
    -用户明确要求根据教材，课本，书本回答
2.general_chat
    用于普通对话。
    
    适用：
    -问候
    -日常闲聊
    -天气
    -与教材无关的问题
    -不需要教材即可回答的问题

用户问题：

{question}

请严格只返回JSON：
{{
    "tool":"tsxtbook_search"或"general_chat"
    "reason":"简短说明为什么使用这个工具"
}}
"""
    try:
        response=client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role":"user",
                    "content":prompt
                }
            ],
            temperature=0.1
        )
        content=response.choices[0].message.content.strip()

        # 处理 Markdown JSON
        if content.startswith("```"):
            content = content.replace("```json", "")
            content = content.replace("```", "")
            content = content.strip()

        result = json.loads(content)

        # 基础校验
        if "tool" not in result:
            raise ValueError("Agent 返回结果缺少 tool")

        if result["tool"] not in [
            "textbook_search",
            "general_chat"
        ]:
            raise ValueError(
                f"Agent 返回了未知 Tool：{result['tool']}"
            )

        result["reason"] = str(
            result.get("reason", "")
        )

        return result

    except Exception as e:
        # 安全兜底
        return {
            "tool": "textbook_search",
            "reason": f"Agent 路由失败，默认搜索教材：{e}"
        }



