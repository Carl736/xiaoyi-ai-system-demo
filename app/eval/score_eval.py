"""
eval 算分脚本：读人工判分后的 results_*.json，输出指标。

用法：
    python app/eval/score_eval.py app/eval/results_20261013_1530.json
"""
import json
import sys#sys：读命令行参数。你执行 python score_eval.py xxx.json 时，sys.argv 就是 ["score_eval.py", "xxx.json"]——[0] 是脚本自己，[1] 是你给的文件。
from collections import Counter
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("用法：python app/eval/score_eval.py app/eval/results_<时间戳>.json")
        sys.exit(1)

    path = Path(sys.argv[1])
    results = json.loads(path.read_text(encoding="utf-8"))

    # 判分完整性检查：还有没填 correct 的题就拒绝算分。
    # 原因：不许"跑完再挑"——指标必须在判分前定死，判分必须全量完成。
    undone = [r["id"] for r in results if r.get("correct") is None]#挑出 correct 还是 None 的，收集 id。因为correct是人工写的，所以需要遍历筛选一下
    if undone:
        print(f"还有 {len(undone)} 道题没判分：{undone}，先填完 correct 再算分")
        sys.exit(1)

    n = len(results)

    # 指标 1：任务完成率 = 答对 / 总数。简历上 Y% 的来源。
    correct = sum(1 for r in results if r["correct"])
    task_rate = correct / n

    # 指标 2：工具选择正确率。
    # expected_tool 为 "none" 的题不参与（纯聊天题不需要工具，谈不上选错）。
    tool_items = [r for r in results if r["expected_tool"] != "none"]#纯聊天题不参与——不需要工具，谈不上选错。
    tool_ok = sum(1 for r in tool_items if r["expected_tool"] in r["tool_calls"])#期望的工具在不在实际调用列表里。在 → 选对了。
    tool_rate = tool_ok / len(tool_items) if tool_items else 0.0

    # 指标 3：平均轮数，给两个口径。
    # truncated=True 的题真实需求轮数未知（只知道 ≥ 上限），
    # 混在一起算平均会低估，所以同时输出"不含截断题"的干净口径。
    iters_all = [r["iterations_used"] for r in results]
    iters_clean = [r["iterations_used"] for r in results if not r["truncated"]]
    avg_all = sum(iters_all) / len(iters_all)
    avg_clean = sum(iters_clean) / len(iters_clean) if iters_clean else 0.0#防除零。如果一道需要工具的题都没有，分母是 0，直接给 0。

    # 指标 4：截断率 = truncated=True / 总数。
    # 太高说明轮数上限卡住了很多题，按"先看分布再动手"的顺序处理。
    trunc_rate = sum(1 for r in results if r["truncated"]) / n

    # 指标 5：无答案题兜底率。
    # correct 由人工判：明确承认"教材里没找到"算对，编了答案算错。
    no_ans = [r for r in results if r["type"] in ("no_answer", "防幻觉")]

    deny_rate = sum(1 for r in no_ans if r["correct"]) / len(no_ans) if no_ans else 0.0

    print(f"测试集：{n} 题（{path.name}）")
    print(f"任务完成率：{correct}/{n} = {task_rate:.1%}")
    print(f"工具选择正确率：{tool_ok}/{len(tool_items)} = {tool_rate:.1%}")
    print(f"平均轮数（含截断题）：{avg_all:.2f}")
    print(f"平均轮数（不含截断题）：{avg_clean:.2f}")
    print(f"截断率：{trunc_rate:.1%}", end="")
    if trunc_rate > 0.2:
        print("  ← 超过 20%，看看被截断的题是在绕圈还是真需要多轮")
    else:
        print()
    if no_ans:
        print(f"无答案题兜底率：{deny_rate:.1%}")

    # 轮数分布：给"5 轮上限怎么定的"准备直方图数据。
    # 如果 90% 的题 2 轮内解决、几乎没有 truncated，5 轮就是合理的上限。
    dist = Counter(r["iterations_used"] for r in results)
    print("轮数分布：", dict(sorted(dist.items())))


if __name__ == "__main__":
    main()
