from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

from app.model.chat_history import ChatHistory
from app.service.agent_service import route_question
from app.service.textbook_tool import textbook_search
from typing import List,Optional
client = OpenAI(
    api_key=settings.settings.deepseek_api_key,
    base_url="https://api.deepseek.com/v1"
)
SIMILARITY_THRESHOLD = 0.7  # 放在文件顶部


#1.通用问答，（不走RAG，用于闲聊/非教材问题）
async def ask_general(qustion:str,db:AsyncSession,user_id:int)->str:
    #不用教材，直接通用回答
    message=[{
        "role":"system",
        "content":"你叫小奕，是一个温柔可爱的高等助教。用户提问的问题和教材无关，请用通用知识友好回答。"
        },
        {
            "role":"user",
            "content":qustion
         }
    ]
    response=client.chat.completions.create(
        model="deepseek-chat",
        messages=message,
        temperature=0.7
    )
    return response.choices[0].message.content


#2.获取历史记录
async def get_chat_history(user_id:int,db:AsyncSession,limit:int=6):
    stmt = (
        select(ChatHistory)
        .where(ChatHistory.user_id == user_id)
        .order_by(ChatHistory.created_at.desc())
        .limit(limit)
    )
    result=await db.execute(stmt)
    history=result.scalars().all()
    return list(reversed(history))

#3.核心问答函数，Agent+RAG
async def ask_question(question:str,db:AsyncSession,user_id:int,document_ids:Optional[List[str]]=None):
    """
    完整的 Agent + Tool + RAG 问答流程：

    用户问题
        ↓
    Agent 路由
        ↓
    ┌───────────────────────┐
    │                       │
    ↓                       ↓
general_chat         textbook_search
    ↓                       ↓
DeepSeek              Embedding
                            ↓
                           FAISS
                            ↓
                      教材检索结果
                            ↓
                        Context
                            ↓
                         DeepSeek
                            ↓
                         最终答案
    """

    # ==========================================
    # 第一步：Agent 决策层
    # ==========================================
    decision=route_question(question)

    tool_name=decision["tool"]

    # ==========================================
    # 第二步：普通聊天
    # ==========================================

    if tool_name =="general_chat":
        return await ask_general(
            question,
            db,
            user_id
        )
    # ==========================================
    # 第三步：调用教材搜索 Tool
    # ==========================================
    elif tool_name=="textbook_search":
        tool_result=textbook_search(
            question=question,
            user_id=user_id,
            document_ids=document_ids,
            top_k=3
        )

    else:
        return"Agent 返回了未知工具"

    # ==========================================
    # 第四步：Tool 没有找到教材内容
    # ==========================================

    if not tool_result:
        return "📚 教材中未找到相关内容。请确认您的问题是否与已上传教材有关，或尝试换个问法。"

    # ==========================================
    # 第五步：获取历史聊天记录
    # ==========================================


    history=await get_chat_history(user_id,db)

    # ==========================================
    # 第六步：构建 messages
    # ==========================================

    messages=[]

    messages.append({
        "role":"system",
         "content":"""
你叫小奕。

你是一个温柔、可爱、聪明的高等数学助教。

你擅长：
- 高等数学
- 线性代数
- 概率论

回答风格：
- 温柔
- 清晰
- 有耐心
- 像学姐

回答教材相关问题时：
1. 优先依据教材资料回答。
2. 不要编造教材中不存在的内容。
3. 如果引用教材内容，请标注页码。
4. 如果教材资料不足，请明确说明。
"""
    })

    # ==========================================
    # 第七步：加入历史对话
    # ==========================================
    for item in history:
        messages.append({
            "role":"user",
            "content":item.question
        })

        messages.append({
            "role":"assistant",
            "content":item.answer
        })
    # ==========================================
    # 第八步：处理 Tool 返回结果
    # ==========================================
    context_parts=[]

    for item in tool_result:
        page=item["page"]
        text=item["text"]

    context_parts.append(
        f"【教材第{page}页】\n{text}"
    )
    context = "\n\n".join(context_parts)

    # ==========================================
    # 第九步：构建最终 Prompt
    # ==========================================

    final_prompt = f"""
    以下内容是教材搜索 Tool 返回的相关教材资料：

    ====================
    {context}
    ====================

    用户问题：

    {question}

    请根据以上教材资料回答用户问题。

    要求：

    1. 优先依据教材资料回答。
    2. 不要编造教材中不存在的内容。
    3. 如果使用教材内容，请标注对应页码。
    4. 如果教材资料不足，请明确说明。
    5. 回答要清晰、易懂，并尽可能解释解题思路。
    """

    messages.append({
        "role": "user",
        "content": final_prompt
    })

    # ==========================================
    # 第十步：调用 DeepSeek 生成最终答案
    # ==========================================

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.7
    )

    return response.choices[0].message.content

