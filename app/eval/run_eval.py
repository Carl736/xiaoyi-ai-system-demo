"""
eval 跑分脚本：加载测试集 → 逐题调 run_agent → 存原始结果。

使用流程（对应 eval计划.md）：
1. 周一：把 30 道题填进 test_set.json（格式见该文件）
2. 周二：python app/eval/run_eval.py
   → 生成 app/eval/results_<时间戳>.json
3. 人工看每题的 answer，给每题填 "correct": true/false
   （30 道题不多，人工判，别用模型判——判分标准不能自己当运动员又当裁判）
4. python app/eval/score_eval.py app/eval/results_<时间戳>.json
   → 输出 5 个指标
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path

from app.db.database import AsyncSessionLocal
from app.service.agent_service import run_agent
from app.service.chat_service import save_chat

# ================= 配置区（跑之前确认这三处） =================
EVAL_DIR = Path(__file__).parent
TEST_SET_PATH = EVAL_DIR / "test_set.json"

# 1. eval 用 user_id=1：教材按 user_id 隔离，只有 user=1 名下有教材，
#    用 999 会导致教材题全部检索为空（已踩坑）。
#    代价是历史污染：run_agent 会读该用户最近 6 条历史。
#    解法：每次跑分前先跑 python -m app.eval.clear_history 清掉历史，
#    保证每题起点一致，控制变量。
#    多轮指代题需要的历史，由下面的 context_turns 机制单独构造。
EVAL_USER_ID =1

# 2. 教材 document_ids：None = 搜该用户全部教材；
#    传 ["doc_id_1", ...] = 只搜这几本。id 跟你上传教材时生成的一致。
DOCUMENT_IDS = None

# 3. 跑分参数。temperature 四档对照 = 改 TEMPERATURE 跑四遍，
#    哪档任务完成率最高，就把哪档写进代码（替换现在的 0.7）。
MAX_ITERATION = 5
TEMPERATURE = 0.7
# =============================================================


async def run_one(question, db, context_turns=None):
    """
    跑一道题。

    context_turns：多轮指代题的前置轮，如 ["泰勒公式是什么？"]。
    先跑前置轮（不计分，只为在 chat_history 里留下历史），
    再跑正式题（如 "它有什么应用？"），这样"它"才有所指。
    没有前置轮的题传 None。

    注意：run_agent 只读历史、不写历史，写历史是 save_chat 的事
    （api/chat.py 里也是 ask_question + save_chat 两步）。
    所以前置轮跑完必须 save，否则历史是空的，前置轮机制失效。
    正式题不 save——历史里只留各题的前置轮（短问题），
    题目之间互相污染最小。
    """
    if context_turns:
        for ctx_q in context_turns:
            ctx_result = await run_agent(
                question=ctx_q,
                user_id=EVAL_USER_ID,
                db=db,
                document_ids=DOCUMENT_IDS,
                max_iteration=MAX_ITERATION,
                temperature=TEMPERATURE,
            )
            # 前置轮必须落库，否则正式题读不到历史
            await save_chat(
                db=db,
                user_id=EVAL_USER_ID,
                question=ctx_q,
                answer=ctx_result["answer"],
            )

    result = await run_agent(
        question=question,
        user_id=EVAL_USER_ID,
        db=db,
        document_ids=DOCUMENT_IDS,
        max_iteration=MAX_ITERATION,
        temperature=TEMPERATURE,
    )
    return result



async def main():
    test_set = json.loads(TEST_SET_PATH.read_text(encoding="utf-8"))#json.loads(...)：把 JSON 字符串转成 Python 的 list。
    print(
        f"测试集：{len(test_set)} 道题，"
        f"temperature={TEMPERATURE}，max_iteration={MAX_ITERATION}"
    )

    results = []

    async with AsyncSessionLocal() as db:
        for i, item in enumerate(test_set, 1):
            #enumerate(test_set, 1)：遍历
            print(f"\n[{i}/{len(test_set)}] {item['id']}：{item['question'][:40]}...")
            #问题太长截前 40 个字，进度条看着清爽
            try:
                r = await run_one(
                    item["question"],
                    db,
                    item.get("context_turns"),
                )
                results.append({
                    "id": item["id"],
                    "type": item["type"],
                    "question": item["question"],
                    "expected_tool": item["expected_tool"],
                    "expected_answer": item["expected_answer"],
                    # 下面是 run_agent 返回的执行数据
                    "answer": r["answer"],
                    "iterations_used": r["iterations_used"],
                    "tool_calls": r["tool_calls"],
                    "truncated": r["truncated"],
                    # 人工判分：看完 answer 后填 true/false，跑脚本时先留 None
                    "correct": None,
                })
            except Exception as e:
                # 单题抛异常不中断整轮跑分，记下来继续下一题
                print(f"  !! 本题抛异常：{e}")
                results.append({
                    "id": item["id"],
                    "type": item["type"],
                    "question": item["question"],
                    "expected_tool": item["expected_tool"],
                    "expected_answer": item["expected_answer"],
                    "answer": f"<异常：{e}>",
                    "iterations_used": 0,
                    "tool_calls": [],
                    "truncated": False,
                    "correct": False,
                })

    ts = datetime.now().strftime("%Y%m%d_%H%M")#strftime("%Y%m%d_%H%M")：当前时间 → 20261013_1530，做文件名。每次跑分独立存档不覆盖——四档对照跑四遍，四个文件摆一起对比。
    out = EVAL_DIR / f"results_{ts}.json"
    out.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n跑完，结果存到 {out.name}")
    print("下一步：人工看每题 answer，填 correct 字段，再跑 score_eval.py")


if __name__ == "__main__":
    asyncio.run(main())
