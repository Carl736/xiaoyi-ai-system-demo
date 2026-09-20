from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.service.textbook_tool import textbook_search
from app.service.calculator_tool import calculate
#它是在告诉 DeepSeek：

#“我这里有一个工具叫 textbook_search，你如果需要，可以调用它。”
#"name": "textbook_search"
#就是告诉模型：
#工具的名字叫 textbook_search
#"description": "搜索用户上传的教材，用于回答教材相关问题"
#这是给 LLM 看 的。
#它帮助模型判断：
#什么情况下应该调用这个工具？
#parameters 是什么？
#它的意思其实非常简单：
#告诉 AI：如果你要调用这个工具，你需要给我什么参数。
TOOLS=[

    # ==========================
    # Tool 1：教材搜索
    # ==========================
    {
    "type":"function",
    "function":{
        "name":"textbook_search",
        "description":"搜索用户上传的教材，用于回答教材相关问题",
        "parameters":{
            "type":"object",
            "properties":{
                "question":{
                    "type":"string",
                    "description":"需要搜索的教材问题"
                },
                "top_k":{
                    "type":"integer",
                    "description":"返回的教材片段数量",
                    "default":3,
                }
            },
            "required":["question"]
        }
    }
},

    # ==========================
    # Tool 2：计算器
    # ==========================
    {
        "type":"function",
        "function":{
            "name":"calculator",
            "description":"计算数学表达式，用于完成精确数学计算",

            "parameters":{
                "type":"object",

                "properities":{
                    "experssion":{
                        "type":"string",
                        "description":"需要计算的数学表达式，例如123*456"
                    }
                },

                "required":["expression"]
            }
        }

    }




]

async def execute_tool(
        tool_name:str,
        arguments:Dict[str,Any],
        user_id:int,
        db:AsyncSession,
):
    if tool_name=="textbook_search":
        return await textbook_search(
            question=arguments["question"],
            user_id=user_id,
            db=db,
            document_ids=None,
            top_k=arguments.get("top_k",3)
        )

    if tool_name=="calculator":
        expression=arguments["expression"]

        result=calculate(expression)

        return {
            "experssion":expression,
            "result":result
        }
    raise ValueError(f"未知 Tool：{tool_name}")