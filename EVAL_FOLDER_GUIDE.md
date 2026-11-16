# app/eval 文件夹代码讲解

## 1. 整体作用

这个目录不是只测某一个函数的单元测试目录，而是做两件事：

1. 用固定题集运行真实 Agent，保存答案、工具调用、循环轮数和截断情况。
2. 直接诊断 RAG 检索链路，例如 FAISS 是否加载、相似度是多少、阈值是否过滤了结果。

完整评测链路是：test_set.json -> clear_history.py（需要时清理历史） -> run_eval.py（逐题调用 Agent） -> results_时间戳.json（保存原始结果） -> 人工填写 correct -> score_eval.py（计算指标）。

diag_*.py 是独立的检索诊断脚本，不负责给 Agent 最终回答评分。

## 2. __init__.py

文件：app/eval/__init__.py

当前为空。它让 app.eval 可以被 Python 当作包，从而支持 python -m app.eval.clear_history。没有业务逻辑。

## 3. test_set.json：固定测试题

文件：app/eval/test_set.json

每个 JSON 对象是一道题，主要字段是：

1. id：题目编号。
2. type：题型，例如计算、单跳、多跳、多轮、防幻觉、模糊提问。
3. question：提交给 Agent 的问题。
4. expected_tool：期望的工具，可能是 calculator、textbook_search 或 none。
5. expected_answer：人工判分时参考的答案要点。
6. context_turns：多轮题的前置问题。
7. note：题目说明。

expected_tool 不是传给模型的参数，而是跑完后比较工具选择是否正确的参考值。

当前题集覆盖：计算题是否调用 calculator、教材题是否调用 textbook_search、教材没有答案时是否承认检索不到、问题模糊时是否追问、多轮指代能否利用历史。

## 4. clear_history.py：控制评测起点

文件：app/eval/clear_history.py

这个脚本只删除评测用户在 PostgreSQL chat_history 表中的聊天记录，条件是 user_id = EVAL_USER_ID。

EVAL_USER_ID = 1，必须和 run_eval.py 中的值一致。

为什么要清理：Agent 会读取最近 6 条历史。上一轮评测留下的内容可能影响下一轮，造成两次结果不可比。

这个脚本不会删除教材，也不会删除 FAISS 向量。

运行方式：python -m app.eval.clear_history

## 5. run_eval.py：批量运行 Agent

文件：app/eval/run_eval.py

### 5.1 启动阶段

脚本导入数据库会话、collect_agent_stream、save_chat 和向量库。

导入 app.model.user.User 虽然没有直接使用，但可以让用户表注册到 SQLAlchemy metadata，避免聊天历史外键找不到目标表。

随后执行 vector_store.load，把磁盘上的 FAISS 索引和 metadata 加载进内存，并打印向量数量。

### 5.2 配置变量

1. EVAL_USER_ID = 1：所有题以这个用户身份执行。
2. DOCUMENT_IDS = None：搜索该用户的全部教材。
3. MAX_ITERATION = 5：每道题最多循环 5 轮。
4. TEMPERATURE = 0.7：传给模型的采样温度。

### 5.3 run_one：运行一道题

函数：app/eval/run_eval.py::run_one

普通题直接调用一次 collect_agent_stream。

有 context_turns 的多轮题会先运行前置问题，用 save_chat 写入问题和答案，再运行正式问题。这样正式问题中的“它”才可能从历史中找到指代对象。

正式问题不在这里保存，只有前置问题保存，这是为了减少题目之间的历史污染。

### 5.4 main：运行整套题

main 读取 test_set.json，使用 enumerate 逐题处理。

正常结果会保存：题目和期望值、Agent 的 answer、iterations_used、tool_calls、truncated、correct=None。

correct 初始为 None，表示还没有人工判分。

如果某题抛异常，try/except 会把异常写入这一题的 answer，并继续下一题。

最后写出 app/eval/results_YYYYMMDD_HHMM.json。

## 6. score_eval.py：读取结果并计算指标

文件：app/eval/score_eval.py

这个脚本不调用模型，也不调用 FAISS，只读取一个已经生成的结果 JSON。

运行方式：python app/eval/score_eval.py 加上结果文件路径。

### 6.1 判分完整性检查

如果还有题目的 correct 是 None，脚本就退出，不计算指标。使用顺序必须是：run_eval.py -> 人工检查 answer 并填写 correct=true 或 false -> score_eval.py。

### 6.2 五类统计

1. 任务完成率：人工判定答对的题数除以总题数。
2. 工具选择正确率：期望工具是否出现在实际 tool_calls 中；expected_tool 为 none 的题不参与。
3. 平均轮数：同时输出包含截断题和排除截断题的两个口径。
4. 截断率：truncated=True 的题数除以总题数。
5. 无答案题兜底率：防幻觉题中，人工判定为正确的比例。

脚本还用 Counter 输出每个轮数出现了多少次，帮助观察 Agent 通常几轮结束。

## 7. diag_retrieval.py：诊断一次 FAISS 检索

文件：app/eval/diag_retrieval.py

它不经过 Agent，直接调用向量库，执行顺序是：

1. 加载 data/vectors/faiss_index。
2. 打印 FAISS 的 ntotal。
3. 打印 metadata 条数。
4. 查看第一条 metadata 的字段、user_id、chunk_id 和文本片段。
5. 把固定问题转成 Embedding。
6. 用 user_id=1、top_k=3、threshold=None 检索，观察原始结果和分数。
7. 再用 threshold=0.7 检索，观察高阈值留下多少结果。

它适合排查：索引是否为空、metadata 是否存在、原始分数是多少、阈值是否过高。

## 8. diag_threshold.py：查看教材题 top-1 分数

文件：app/eval/diag_threshold.py

它筛出 expected_tool 为 textbook_search 的题，批量生成 Embedding，并对每题进行不设阈值的 top_k=3 检索。

多轮题会把 context_turns 和当前问题拼接，近似模拟 Agent 看到的完整上下文。

脚本打印题目 ID、第一名结果的相似度和第一名 chunk 的文本片段。

用途是观察真实题目的分数分布，辅助判断阈值是否太高或太低。

## 9. diag_threshold2.py：扫描多个阈值

文件：app/eval/diag_threshold2.py

这个脚本使用手写的 ANSWER_KEY，记录每道题的正确内容在哪一章；使用 HALLU 列表记录防幻觉题。

它先不设置阈值检索 top 3，再根据返回文本前 20 个字符中是否出现章节名，记录各章节分数。

随后扫描 0.2、0.25、0.3、0.35、0.4、0.5 等阈值，并统计：

1. 正常教材题的正确章节分数是否仍达到阈值。
2. 防幻觉题的最高分是否低于阈值，从而返回空结果。

它是阈值诊断脚本，不是通用 Recall@K 实现，因为它依赖手工章节映射、只看 top 3，还依赖文本前 20 个字符的章节标记。

## 10. results_*.json：历史结果快照

目录里的 results_时间.json 是 run_eval.py 过去运行得到的历史文件。

它们保存当时的 Agent 回答、实际工具调用、实际循环轮数、是否截断和人工判分状态。

它们不会自动参与下一次评测，只有传给 score_eval.py 时才会被读取。

## 11. 一次完整评测的顺序

1. 确认 user_id=1 的教材和 FAISS 索引存在。
2. 运行 python -m app.eval.clear_history。
3. 检查 test_set.json。
4. 运行 python -m app.eval.run_eval。
5. 打开新生成的 results_*.json。
6. 人工给每题填写 correct。
7. 运行 python app/eval/score_eval.py 加上结果文件路径。
8. 查看任务完成率、工具选择正确率、平均轮数、截断率和兜底率。

## 12. 当前目录没有实现的功能

根据当前代码，这个目录没有实现：

1. 自动让大模型判断答案是否正确。
2. 自动计算 Recall@K。
3. 自动比较多个 MAX_ITERATION 配置。
4. 自动调整相似度阈值。
5. 自动修改 Agent 或 FAISS 代码。

它的职责是：固定题集、运行 Agent、保存结果、人工判分后统计，以及诊断 RAG 检索。
