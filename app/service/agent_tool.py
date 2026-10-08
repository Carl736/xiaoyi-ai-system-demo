from typing import Dict, Any, Optional, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.service.textbook_tool import textbook_search
from app.service.calculator_tool import calculator


# ============================================================
# Tool Definitions
# ============================================================

TOOLS = [

    # ========================================================
    # Tool 1：教材搜索
    # ========================================================

    {
        "type": "function",

        "function": {
            "name": "textbook_search",

            "description": (
                "搜索用户上传的教材，用于回答教材相关问题。"
                "当用户询问教材内容、知识点、例题、章节、"
                "教材中的解题方法，或者明确要求根据教材回答时使用。"
            ),

            "parameters": {
                "type": "object",

                "properties": {

                    "question": {
                        "type": "string",
                        "description": "需要搜索的教材问题"
                    },

                    "top_k": {
                        "type": "integer",
                        "description": "返回的教材片段数量",
                        "default": 3
                    }
                },

                "required": [
                    "question"
                ]
            }
        }
    },


    # ========================================================
    # Tool 2：计算器
    # ========================================================

    {
        "type": "function",

        "function": {
            "name": "calculator",

            "description": (
                "计算数学表达式，用于完成精确数学计算。"
                "例如：123*456、2**10、(3+5)*2。"
            ),

            "parameters": {
                "type": "object",

                "properties": {

                    "expression": {
                        "type": "string",
                        "description": (
                            "需要计算的数学表达式，"
                            "例如 123*456"
                        )
                    }
                },

                "required": [
                    "expression"
                ]
            }
        }
    }
]


# ============================================================
# Tool Executor
# ============================================================

async def execute_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    user_id: int,
    db: AsyncSession,
    document_ids: Optional[List[str]] = None,
):
    """
    Agent Tool 执行器。

    根据 Tool Name 将大模型的 Tool Call
    分发给对应的具体 Tool。
    """

    # ========================================================
    # textbook_search
    # ========================================================

    if tool_name == "textbook_search":

        return await textbook_search(
            question=arguments["question"],
            user_id=user_id,
            db=db,
            document_ids=document_ids,
            top_k=arguments.get("top_k", 3),
        )


    # ========================================================
    # calculator
    # ========================================================

    if tool_name == "calculator":

        expression = arguments["expression"]

        return calculator(expression)


    # ========================================================
    # Unknown Tool
    # ========================================================

    raise ValueError(
        f"未知 Tool：{tool_name}"
    )