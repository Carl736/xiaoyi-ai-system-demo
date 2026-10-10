"""
eval 前清空评测用户的聊天记录，保证每次跑分起点一致。

为什么需要？
run_agent 每次会读该用户最近 6 条历史。上次跑分残留的
"泰勒公式→检索为空"会被模型看到，它可能偷懒复用历史结论、
跳过 textbook_search，导致两次跑分行为不一致、指标不可比。

只删 chat_history 表，不动教材：
教材存在向量库里（按 user_id 隔离），清聊天记录不影响检索。

用法（项目根目录，先清后跑）：
    python -m app.eval.clear_history
    python -m app.eval.run_eval
"""

import asyncio

from sqlalchemy import text

from app.db.database import AsyncSessionLocal

# 必须跟 run_eval.py 里的 EVAL_USER_ID 一致
EVAL_USER_ID = 1


async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            # text() 写原生 SQL：不用猜 ChatHistory 的 model 路径，
            # 表名 chat_history 从 SQLAlchemy 日志里确认过。
            text("DELETE FROM chat_history WHERE user_id = :uid"),
            {"uid": EVAL_USER_ID},
        )
        await db.commit()
        print(
            f"已清空 user_id={EVAL_USER_ID} 的聊天记录，"
            f"共 {result.rowcount} 条"
        )


if __name__ == "__main__":
    asyncio.run(main())
