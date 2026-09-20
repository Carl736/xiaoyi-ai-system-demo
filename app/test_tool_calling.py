import asyncio

from app.service.agent_service import run_agent
from app.db.database import AsyncSessionLocal


async def main():

    async with AsyncSessionLocal() as db:

        print("\n==============================")
        print("测试 1：普通聊天")
        print("==============================")

        result = await run_agent(
            question="你好呀",
            user_id=1,
            db=db,
        )

        print("最终回答：")
        print(result)

        print("\n==============================")
        print("测试 2：教材问题")
        print("==============================")

        print("\n==============================")
        print("测试 3：计算问题")
        print("==============================")

        result = await run_agent(
            question="123乘以456等于多少？",
            user_id=1,
            db=db,
        )
        print("\n==============================")
        print("测试 4：计算器异常")
        print("==============================")

        result = await run_agent(
            question="123除以0等于多少？",
            user_id=1,
            db=db,
        )
        print("\n==============================")
        print("测试 5：非法数学表达式")
        print("==============================")

        result = await run_agent(
            question="帮我计算 123 / abc",
            user_id=1,
            db=db,
        )

        print("最终回答：")
        print(result)
        print("最终回答：")
        print(result)
        print("最终回答：")
        print(result)


if __name__ == "__main__":
    asyncio.run(main())