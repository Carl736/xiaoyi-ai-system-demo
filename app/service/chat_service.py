from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.chat_schema import Question
from app.config import settings
from app.utils.embedding import get_embedding
from app.vectorstore.faiss_db import vector_store
from app.model.chat_history import ChatHistory
from app.service.agent_service import should_search_textbook
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
       完整的 Agent 决策 + RAG 问答流程：

       用户问题
          ↓
       Agent 判断：要不要搜教材？
          ↓
       不需要 → 直接通用问答
       需要   → RAG 检索 + 阈值过滤 + LLM 生成
       """

    # ==========================================
    # 第一步：Agent 决策层
    # ==========================================
    desecion=should_search_textbook(question)

    if not desecion.get("need_search",True):
        # 不需要搜教材，直接通用问答
        return await ask_general(question,db,user_id)

    # ==========================================
    # 第二步：获取历史记录（用于上下文）
    # ==========================================

    history=await get_chat_history(user_id,db)

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
"""
    })
    for item in history:
        messages.append({
            "role":"user",
            "content":item.question
        })

    # ==========================================
    # 第三步：向量检索（带阈值过滤）
    # ==========================================
    q_vec = get_embedding(question)#将文本根据预训练模型转化为对应向量

    docs = vector_store.search(
        q_vec,
        top_k=3,
        user_id=user_id,
        document_ids=document_ids,
        threshold=SIMILARITY_THRESHOLD# 👈 加上阈值
    )#搜索相似的三个



    # ==========================================
    # 第四步：构建上下文（有/无检索结果）
    # ==========================================
    if docs:

        context_parts = []

        for d in docs:
            page_info = f"【第{d['page']}页】"

            context_parts.append(
                f"{page_info}{d['text']}"
            )

        context = "\n\n".join(
            context_parts
        )
    else:
        # 没有检索到相关内容 → 直接返回“不知道”
        return "📚 教材中未找到相关内容。请确认您的问题是否与已上传教材有关，或尝试换个问法。"
    final_prompt = f"""
    教材资料：
    {context}

    用户问题：
    {question}

    请结合教材内容回答，如果引用了教材内容，在末尾标注页码。
    """

    messages.append({
        "role": "user",
        "content": final_prompt
    })

    # ==========================================
    # 第六步：调用 DeepSeek
    # ==========================================
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.7
    )

    return response.choices[0].message.content

# ==========================================
# 4. 保存聊天记录（保留原有逻辑）
# ==========================================
async def save_chat(user_id:int,question:str,answer:str,db:AsyncSession):
    #首先创建一个 ChatHistory 实例然后调用 db.add() 方法将这个实例添加到数据库会话中，最后调用 db.commit() 方法来提交事务，将数据保存到数据库中。
    chat_history=ChatHistory(
        user_id=user_id,
        question=question,
        answer=answer
    )
    db.add(chat_history)
    await db.commit()
    await db.refresh(chat_history)
    return chat_history




