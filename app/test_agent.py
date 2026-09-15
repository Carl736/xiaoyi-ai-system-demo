# test_agent.py（放在项目根目录）
import sys
import os

# 把项目根目录加入路径，方便导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.service.agent_service import should_search_textbook

# ==========================================
# 测试问题列表
# ==========================================
test_cases = [
    ("什么是泰勒公式？", True),
    ("请解释导数与微分的关系", True),
    ("罗尔定理的条件是什么", True),
    ("计算 ∫x² dx", True),
    ("高等数学第二讲讲了什么", True),
    ("今天天气怎么样？", False),
    ("你好吗？", False),
    ("你叫什么名字？", False),
    ("给我讲个笑话", False),
    ("如何做红烧肉？", False),
]

# ==========================================
# 运行测试
# ==========================================
print("=" * 60)
print("Agent 决策测试")
print("=" * 60)

correct = 0
total = len(test_cases)

for question, expected in test_cases:
    result = should_search_textbook(question)
    need_search = result.get("need_search", False)#result是一个字典，get函数的作用是：如果字典里有这个键，就返回对应的值；如果没有，就返回默认值，这里默认值是False
    reason = result.get("reason", "无理由")#get函数的作用是：如果字典里有这个键，就返回对应的值；如果没有，就返回默认值，这里默认值是"无理由"

    status = "✅" if need_search == expected else "❌"
    print(f"{status} 问题：{question}")
    print(f"   决策：{'需要搜教材' if need_search else '不需要搜教材'}（预期：{'需要' if expected else '不需要'}）")
    print(f"   理由：{reason}")
    print()

    if need_search == expected:
        correct += 1

print("=" * 60)
print(f"准确率：{correct}/{total} = {correct/total*100:.1f}%")
print("=" * 60)