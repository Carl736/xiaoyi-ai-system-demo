# test_agent.py

from app.service.agent_service import route_question
from app.service.textbook_tool import textbook_search


def test_router():
    """测试 Agent 路由"""

    print("=" * 60)
    print("第一部分：测试 Agent Router")
    print("=" * 60)

    questions = [
        "你好呀",
        "你叫什么名字？",
        "泰勒公式是什么？",
        "教材中的洛必达法则怎么使用？",
        "书上第三章主要讲什么？",
    ]

    for question in questions:

        print(f"\n用户问题：{question}")

        result = route_question(question)

        print(f"选择 Tool：{result.get('tool')}")
        print(f"判断理由：{result.get('reason')}")


def test_textbook_tool():
    """测试教材搜索 Tool"""

    print("\n")
    print("=" * 60)
    print("第二部分：测试 Textbook Search Tool")
    print("=" * 60)

    question = "泰勒公式是什么？"

    # 这里先使用测试用户 ID
    user_id = 1

    print(f"\n用户问题：{question}")
    print(f"用户 ID：{user_id}")

    result = textbook_search(
        question=question,
        user_id=user_id,
        document_ids=None,
        top_k=3
    )

    if not result:

        print("\n❌ 没有搜索到教材内容")
        return

    print(f"\n✅ 搜索到 {len(result)} 条教材内容")

    for index, item in enumerate(result, start=1):

        print("\n" + "-" * 60)

        print(f"结果 #{index}")

        print(f"页码：{item.get('page')}")

        print(f"来源：{item.get('source')}")

        print(f"相似度：{item.get('score')}")

        print(f"document_id：{item.get('document_id')}")

        print("\n教材内容：")

        print(item.get("text"))


if __name__ == "__main__":

    # 测试 Agent Router
    test_router()

    # 测试教材搜索 Tool
    test_textbook_tool()