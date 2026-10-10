import asyncio
from typing import Dict, Any, Optional, List
from app.service.textbook_tool import textbook_search, SIMILARITY_THRESHOLD
from sqlalchemy.ext.asyncio import AsyncSession
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
            threshold=arguments.get(
                "threshold",
                SIMILARITY_THRESHOLD,
            ),
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

# ============================================================
# Tool 兜底层：重试 → 降级 → 明确失败
# ============================================================

# 值得重试的瞬时错误：DB 连接抖动、超时等基础设施问题。
# 业务错误（PermissionError / ValueError）不重试，直接抛给上层。
# 注意：工具"正常返回空结果"不是异常，不走重试，走下面的降级。
RETRYABLE_ERRORS = (
    TimeoutError,
    ConnectionError,
    OSError,
)

MAX_RETRIES = 2          # 最多重试 2 次（共 3 次尝试）
RETRY_BASE_DELAY = 1.0   # 退避基数（秒）：第 1 次等 1s，第 2 次等 2s

# 降级参数：放宽到什么程度目前是拍脑袋定的，
# 后续可以用 eval 对照（0.5 / 0.6 / 0.7）验证
DEGRADED_THRESHOLD = 0.5


async def _execute_with_retry(
    tool_name: str,
    arguments: Dict[str, Any],
    user_id: int,
    db: AsyncSession,
    document_ids: Optional[List[str]] = None,
):
    """带指数退避重试的原始 tool 调用，只重试瞬时错误。"""
    last_exc = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            return await execute_tool(
                tool_name=tool_name,
                arguments=arguments,
                user_id=user_id,
                db=db,
                document_ids=document_ids,
            )
        except RETRYABLE_ERRORS as e:
            last_exc = e
            if attempt < MAX_RETRIES:
                await asyncio.sleep(
                    RETRY_BASE_DELAY * (2 ** attempt)
                )

    raise last_exc


async def execute_tool_resilient(
    tool_name: str,
    arguments: Dict[str, Any],
    user_id: int,
    db: AsyncSession,
    document_ids: Optional[List[str]] = None,
):
    """
    带兜底的 tool 执行，顺序是硬性的：

    1. 瞬时错误 → 指数退避重试（最多 2 次）
    2. textbook_search 正常返回空 → 降级：
       top_k 翻倍、阈值降到 0.5，再查一次
    3. 仍无结果 / 参数错误 → 返回明确标注的失败，
       让 LLM 按 system prompt 走 fallback
       （明确说"教材里没找到" + 通用知识补充并区分标注）
    """

    # ==========================================
    # 1. 带重试执行一次
    # ==========================================

    result = await _execute_with_retry(
        tool_name=tool_name,
        arguments=arguments,
        user_id=user_id,
        db=db,
        document_ids=document_ids,
    )

    # ==========================================
    # 2. textbook_search 返回空 → 降级
    # ==========================================

    if (
        tool_name == "textbook_search"
        and isinstance(result, list)
        and not result
    ):
        degraded_args = dict(arguments)
        degraded_args["top_k"] = arguments.get("top_k", 3) * 2
        degraded_args["threshold"] = DEGRADED_THRESHOLD
        print(">>> 触发降级：top_k 翻倍，阈值降到 0.5，重查一次")

        degraded = await _execute_with_retry(
            tool_name=tool_name,
            arguments=degraded_args,
            user_id=user_id,
            db=db,
            document_ids=document_ids,
        )

        if degraded:
            return {
                "success": True,
                "degraded": True,
                "note": (
                    "首次检索无结果，已放宽检索条件 "
                    "(top_k 翻倍、相似度阈值降至 0.5) "
                    "后得到以下结果。"
                ),
                "results": degraded,
            }

        return {
            "success": True,
            "degraded": True,
            "results": [],
            "note": (
                "已尝试放宽检索条件，教材中仍没有检索到"
                "相关内容。请明确告诉用户当前上传的教材中"
                "没有相关内容，不要编造教材来源。"
            ),
        }

    # ==========================================
    # 3. calculator 参数错误 → 不重试，直接报
    # ==========================================

    if (
        tool_name == "calculator"
        and isinstance(result, dict)
        and "error" in result
    ):
        return {
            "success": False,
            "error": "invalid_expression",
            "message": (
                f"计算表达式不合法：{result['error']}。"
                "请修正 expression 后重新调用 calculator。"
            ),
        }

    # ==========================================
    # 4. 正常成功，原样返回
    # ==========================================

    return result
