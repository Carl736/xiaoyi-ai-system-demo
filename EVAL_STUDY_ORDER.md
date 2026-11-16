# eval 文件夹复习顺序

## 1. 先记住评测目的

eval 不是只测试程序有没有报错，而是回答：

1. Agent 最终回答是否正确？
2. 是否选择了正确工具？
3. 是否调用了太多轮？
4. 没有教材答案时，是否避免编造？
5. RAG 检索不到时，问题出在索引、分数、阈值还是过滤？

总链路：固定题集 → 清理历史 → 运行 Agent → 保存原始结果 → 人工判分 → 统计指标 → 单独诊断检索。

## 2. 第一遍看 test_set.json

文件：app/eval/test_set.json

重点看四个字段：

1. question：实际问 Agent 的问题。
2. expected_tool：期望调用哪个工具。
3. expected_answer：人工判断答案时参考什么。
4. context_turns：多轮题的前置上下文。

题型包括计算题、教材题、防幻觉题、模糊题和多轮指代题。

要理解：expected_tool 不是传给模型的参数，而是跑完后比较工具选择是否正确的参考值。

## 3. 第二遍看 clear_history.py

文件：app/eval/clear_history.py

它只删除评测用户在 PostgreSQL chat_history 表中的聊天记录。EVAL_USER_ID = 1，必须和 run_eval.py 一致。

为什么清理：Agent 会读取最近 6 条历史。上一轮评测留下的内容可能影响下一轮，造成两次结果不可比。

它不删除教材，也不删除 FAISS 向量。

## 4. 第三遍看 run_eval.py 的配置区

文件：app/eval/run_eval.py

1. EVAL_USER_ID = 1：用哪个用户身份评测。
2. DOCUMENT_IDS = None：搜索该用户全部教材。
3. MAX_ITERATION = 5：每道题最多循环几轮。
4. TEMPERATURE = 0.7：模型采样温度。

这一步要理解：评测必须固定用户、教材、题集和参数，否则不同结果不能直接比较。

## 5. 第四遍看 run_one()

普通题：问题 → collect_agent_stream → 得到最终结果。

多轮题：context_turns 前置问题 → 调用 Agent → save_chat 保存前置问答 → 再运行正式问题。

关键事实：Agent 负责读取历史，但不会自动把本次结果写入历史；保存历史是 save_chat 做的。

## 6. 第五遍看 run_eval.py 的 main()

main 的顺序：

1. 读取 test_set.json。
2. 遍历每一道题。
3. 调用 run_one()。
4. 记录 Agent 返回字段。
5. 单题异常时记录异常并继续下一题。
6. 写出 results_时间戳.json。

每道结果重点看：answer、tool_calls、iterations_used、truncated 和 correct。

correct 初始为 None，表示还没有人工判分。

## 7. 第六遍看一个 results_*.json

每道题按这个顺序看：

1. 问题是什么？
2. 期望工具是什么？
3. 实际调用工具是什么？
4. 最终答案是否符合 expected_answer？
5. 用了几轮？
6. 是否截断？
7. correct 是否已填写？

要区分：工具选对，不等于最终答案一定答对。

## 8. 第七遍看 score_eval.py

文件：app/eval/score_eval.py

它不调用模型，只读取结果文件并统计。

五个指标：

1. 任务完成率：答对题数除以总题数。
2. 工具选择正确率：期望工具是否出现在实际工具列表中。
3. 平均轮数：Agent 平均用了几轮。
4. 截断率：多少题达到最大迭代轮数。
5. 无答案题兜底率：防幻觉题中有多少正确承认检索不到。

最后看轮数分布，判断 Agent 通常在第几轮结束。

## 9. 第八遍看 diag_retrieval.py

文件：app/eval/diag_retrieval.py

它是单次底层检索排查，不经过 Agent。按输出顺序理解：

1. FAISS 是否成功加载。
2. ntotal 是否大于 0。
3. metadata 是否有内容。
4. metadata 是否有 user_id 和 chunk_id。
5. 不设阈值时原始分数是多少。
6. 设置高阈值后结果还剩多少。

它回答：是索引没有内容，还是结果被阈值过滤了？

## 10. 第九遍看 diag_threshold.py

文件：app/eval/diag_threshold.py

它批量查看教材题的 top-1 相似度：

1. 只筛 expected_tool 为 textbook_search 的题。
2. 多轮题把前置上下文拼进查询。
3. 检索时 threshold=None，先看原始分数。
4. 输出每题第一名的分数和 chunk 片段。

用途：观察正常教材题的相似度分布。

## 11. 第十遍看 diag_threshold2.py

文件：app/eval/diag_threshold2.py

它扫描多个阈值，比较：

1. 正常教材题的正确 chunk 是否还能留下。
2. 防幻觉题是否能保持空结果。

限制：

1. ANSWER_KEY 是人工写的章节映射。
2. 只看 top 3。
3. 通过文本前 20 个字符识别章节。
4. 不是完整的 Recall@K 自动评测。

## 12. 最后练习一条完整讲解顺序

1. test_set.json 定义题目、期望工具和参考答案。
2. 评测前清掉指定用户的历史，保证每次起点一致。
3. run_eval.py 逐题调用 collect_agent_stream。
4. 多轮题先运行前置问题并保存历史，再运行正式问题。
5. 每题保存答案、工具调用、轮数、截断状态和待人工填写的 correct。
6. 人工判完后，score_eval.py 统计完成率、工具选择率、平均轮数、截断率和兜底率。
7. 如果怀疑 RAG 有问题，再用三个 diag 脚本分别检查索引、原始分数和阈值。

## 13. 复习完成标准

你能回答下面的问题，就说明基本掌握：

1. 为什么评测前要清聊天历史？
2. expected_tool 和 tool_calls 有什么区别？
3. 为什么 correct 需要人工填写？
4. iterations_used 和 MAX_ITERATION 有什么区别？
5. truncated=True 代表什么？
6. 为什么 diag_retrieval.py 不经过 Agent？
7. 为什么阈值诊断要先用 threshold=None？
8. 为什么不能只看平均轮数判断 Agent 好不好？
