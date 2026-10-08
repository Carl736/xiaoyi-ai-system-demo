import asyncio

from app.db.database import AsyncSessionLocal
from app.service.textbook_tool import textbook_search


async def test_textbook_search():
    # 修改成你数据库中真实存在的用户 ID
    user_id = 1

    # 如果想测试指定教材，就填真实的 document_id
    # 暂时不知道的话可以先设为 None
    document_ids = None

    question = "什么是泰勒公式？"

    async with AsyncSessionLocal() as db:

        results = await textbook_search(
            question=question,
            user_id=user_id,
            db=db,
            document_ids=document_ids,
            top_k=3,
        )

        print("\n==============================")
        print("教材检索测试")
        print("==============================")

        print(f"问题：{question}")
        print(f"用户 ID：{user_id}")
        print(f"返回数量：{len(results)}")

        if not results:
            print("\n❌ 没有检索到教材内容")
            return

        print("\n✅ 检索成功")

        for i, result in enumerate(results, start=1):
            print(f"\n---------- 结果 {i} ----------")

            print("text：")
            print(result.get("text"))

            print("\npage：")
            print(result.get("page"))

            print("\nsource：")
            print(result.get("source"))

            print("\ndocument_id：")
            print(result.get("document_id"))

            print("\nscore：")
            print(result.get("score"))


if __name__ == "__main__":
    asyncio.run(test_textbook_search())