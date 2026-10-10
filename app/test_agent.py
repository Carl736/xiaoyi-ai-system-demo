import asyncio

from app.db.database import AsyncSessionLocal
from app.model.user import User
from app.service.agent_service import run_agent
from app.service.chat_service import save_chat


async def test_agent():

    async with AsyncSessionLocal() as db:

        # ==========================================
        # 测试 1：普通聊天 + Memory
        # ==========================================

        print("\n==============================")
        print("测试 1：普通聊天 + Memory")
        print("==============================")

        question1 = "你好，你叫什么名字？"

        # run_agent 现在返回 dict，["answer"] 才是答案字符串
        result1 = await run_agent(
            question=question1,
            user_id=1,
            db=db,
        )
        answer1 = result1["answer"]

        print("\n用户：", question1)
        print("小奕：", answer1)

        await save_chat(
            db=db,
            user_id=1,
            question=question1,
            answer=answer1,
        )

        # ==========================================
        # 测试 2：Calculator Tool
        # ==========================================

        print("\n==============================")
        print("测试 2：Calculator Tool")
        print("==============================")

        question2 = "帮我计算 123 × 456"

        # run_agent 现在返回 dict，["answer"] 才是答案字符串
        result2 = await run_agent(
            question=question2,
            user_id=1,
            db=db,
        )
        answer2 = result2["answer"]

        print("\n用户：", question2)
        print("小奕：", answer2)

        await save_chat(
            db=db,
            user_id=1,
            question=question2,
            answer=answer2,
        )

        # ==========================================
        # 测试 3：教材 Tool
        # ==========================================

        print("\n==============================")
        print("测试 3：Textbook Search Tool")
        print("==============================")

        question3 = "教材中的泰勒公式是什么？"

        # run_agent 现在返回 dict，["answer"] 才是答案字符串
        result3 = await run_agent(
            question=question3,
            user_id=1,
            db=db,
        )
        answer3 = result3["answer"]

        print("\n用户：", question3)
        print("小奕：", answer3)

        await save_chat(
            db=db,
            user_id=1,
            question=question3,
            answer=answer3,
        )


if __name__ == "__main__":
    asyncio.run(test_agent())
