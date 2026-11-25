from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.model.chat_history import ChatHistory
from app.model.user_memory import UserMemory
from app.model.chat_summary import ChatSummary
import json

from app.core.llm_client import client

#短期记忆
async def get_chat_history(
        user_id:int,
        db:AsyncSession,
        limit:int=6,
)->List[ChatHistory]:
    """
    获取用户最近的聊天记录。

    limit 表示最多获取多少条历史消息记录。
    例如：
        limit=6
        表示获取最近 6 次问答。
        按时间从旧到新
    """
    stmt=(
        select(ChatHistory)
        .where(ChatHistory.user_id==user_id)
        .order_by(ChatHistory.created_at.desc())
        .limit(limit)
    )

    result=await db.execute(stmt)

    history=result.scalars().all()
    # 数据库是倒序：
    #
    # 最新
    # ↓
    # 第6次
    # 第5次
    # 第4次
    # ...
    #
    # 但 LLM 需要按照真实对话顺序阅读：
    #
    # 第1次
    # 第2次
    # 第3次
    # ...
    # 第6次
    #
    return list(reversed(history))

#长期顺序
async def get_user_memories(
        user_id:int,
        db:AsyncSession,
        limit
):
    stmt=(
        select(UserMemory)
        .where(UserMemory.user_id==user_id)
        .order_by(UserMemory.created_at.desc())
        .limit(limit)
    )
    result=await db.execute(stmt)

    memories=result.scalars().all()

    return memories


#写入长期记忆
async def create_user_memory(
        user_id:int,
        content:str,
        db:AsyncSession,
):
    memory=UserMemory(
        user_id=user_id,
        content=content
    )
    db.add(memory)

    await db.flush()

    return memory

async def extract_user_memories(question:str)->list[str]:
    prompt=f"""
从下面这句话中，只提取明确用户表达，适合长期保存的个人事实或稳定偏好。
不要推断，不要提取普通知识或临时要求。
只返回JSON字符串数组；没有可保存内容是返回[]。
用户输入：
{question}
"""
    response=await client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role":"system",
                "content":"你是一个谨慎的用户长期记忆抽取器，智能提取用户明确表达的信息"
            },
            {
                "role":"user",
                "content":prompt,
            },
        ],
        temperature=0,
    )

    raw_content=response.choices[0].message.content or "[]"
    memories=json.loads(raw_content)

    if not isinstance(memories,list):
        return []

    return[
        memory.strip()
        for memory in memories
        if isinstance(memory, str) and memory.strip()
    ]

#字符数粗略估算预算
def select_history_with_budget(history:list[ChatHistory],history_budget:int = 3000):
    save_history = []
    cut_history=[]
    total = 0
    for index, cut in enumerate(history[::-1]):
        total += len(cut.answer) + len(cut.question)

        if index == 0 and len(cut.answer) + len(cut.question) >= history_budget:
            save_history.append(cut)
            continue

        if total <= history_budget:
            save_history.append(cut)
            continue

        cut_history.append(cut)

    cut_history.reverse()
    save_history.reverse()
    return cut_history,save_history

#读取摘要函数
async def get_recent_summary(
        user_id:int,
        db:AsyncSession,
)->ChatSummary:
    stmt=(select(ChatSummary)
          .where(ChatSummary.user_id==user_id)
          )
    result=await db.execute(stmt)
    summary=result.scalar_one_or_none()
    return summary

#创建或更新摘要
async def create_or_update_summary(
        user_id:int,
        content:str,
        covered_through_chat_id:int,
        db:AsyncSession
):
    summary=await get_recent_summary(
        user_id=user_id,
        db=db,
    )
    if summary is None:
        chat_summary=ChatSummary(
            user_id=user_id,
            content=content,
            covered_through_chat_id=covered_through_chat_id
        )
        db.add(chat_summary)
        await db.flush()
        return chat_summary
    else:
        summary.covered_through_chat_id=covered_through_chat_id
        summary.content=content
        await db.flush()
        return summary



#摘要生成函数：把旧摘要+新被削掉的问答交给模型压缩
async def summary_process(
        previous_summary: str | None,#之前摘要
        cut_history:list[ChatHistory],#这一轮被削掉的问答
):
    dialogue_parts=[]
    for cut_his in cut_history:
        dialogue_parts.append(
            f"用户：{cut_his.question}\n助手：{cut_his.answer}"
        )
    dialogue_text="\n".join(dialogue_parts)

    prompt=f"""
你是摘要生成模型，你负责提取给你的已有摘要和用户问答，浓缩成短期对话摘要，
不要推断，不要提取无效信息，
保留对后续对话有用的目标、事实和未解决问题，省略寒暄和重复内容；
不要抽取长期用户画像：
已有摘要{previous_summary or "暂无旧摘要"}
用户问答:{dialogue_text}
"""
    response=await client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role":"system",
                "content":"你是一个谨慎的用户摘要提取器，智能提取用户之前残留的信息并进行压缩"
            },
            {
                "role":"user",
                "content":prompt
            },
        ],
        temperature=0,

    )
    result=response.choices[0].message.content

    if not result or not result.strip():
        raise ValueError(
            "摘要失败，提取结果为空"
        )

    return result.strip()
