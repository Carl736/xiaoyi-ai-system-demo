# Agent 开发岗面试突击速记

## 1. 单头注意力

注意力让模型判断当前 token 应该关注输入中的哪些位置。

输入隐藏向量经过三组线性变换得到：

1. Q：Query，当前查询需求。
2. K：Key，每个位置用于匹配的特征。
3. V：Value，匹配后真正取回的内容。

公式：Attention(Q,K,V) = softmax(QK^T / sqrt(d_k))V。

流程：Q 和 K 点积得到匹配分数，除以 sqrt(d_k) 控制数值尺度，softmax 得到权重，再用权重加权 V。

除以 sqrt(d_k) 的原因：维度越大，点积数值可能越大；直接进入 softmax 会让概率过度集中、梯度变小、训练不稳定。

单头只有一套 Q、K、V 投影，在一个表示子空间里学习关系。

## 2. 多头注意力

多头注意力把隐藏维度分成多个子空间，每个头有自己的一套 Q、K、V 投影，多个头并行计算，最后拼接并做输出投影。

一个头可能关注主谓关系，另一个头关注代词指代，另一个头关注远距离主题关系。

多头的多，指多组参数、多种子空间和多种注意力关系，不是把同一个结果简单复制。

对比：单头关注一种关系，多头可以并行捕获多种关系。

## 3. Transformer

Transformer 是以注意力为核心的序列模型结构，常见组成包括：

1. Token embedding 和位置编码。
2. Multi-Head Self-Attention。
3. 残差连接和 LayerNorm。
4. 前馈网络 FFN。
5. 多层堆叠。

Encoder 通常能看到完整输入，适合理解、分类和 Embedding。

Decoder 使用因果遮罩，只看当前和之前的 token，逐步预测下一个 token，适合文本生成和工具调用参数生成。

## 4. 小奕里的模型分工

MiniLM：Encoder 方向的句向量模型。

1. 文档 chunk 经过 MiniLM 变成向量。
2. 用户问题经过同一个 MiniLM 变成查询向量。
3. FAISS 比较向量相似度。

DeepSeek：项目中用于对话生成和工具调用的 Decoder-style 模型。

1. 接收 system prompt、历史、当前问题和工具 schema。
2. 生成普通回答或 tool_call。
3. 读取工具结果后继续下一轮生成。

## 5. LangChain

LangChain 是构建 LLM 应用的组件和抽象框架，常见组件包括：

1. Prompt 模板。
2. Model 封装。
3. Tool 封装。
4. Retriever 检索器。
5. Chain 链式调用。
6. Memory 或消息管理。

它更像一套应用开发组件和高层抽象。

当前项目 requirements.txt 有 LangChain 相关依赖，但 app 代码没有找到实际导入和调用。小奕当前是直接使用 OpenAI 兼容客户端调用 DeepSeek，并自己编排工具。

## 6. LangGraph

LangGraph 是用于编排有状态 Agent 工作流的图框架。

核心概念：

1. State：共享状态。
2. Node：执行工作的函数。
3. Edge：决定下一步走哪个节点。

典型图：

LLM 节点 → 有 tool_call 就到工具节点 → 工具结果回到 LLM 节点；没有 tool_call 就结束。

小奕没有使用 LangGraph API，但 run_agent_stream 的手写 for 循环可以概念映射为 State、LLM Node、Tool Node 和条件边。

区别：LangChain 偏组件和链，LangGraph 偏状态、分支和循环编排。

## 7. 状态机

状态机由三部分组成：

1. 当前状态。
2. 触发事件。
3. 合法状态转换规则。

例如：PENDING + 开始处理 → PROCESSING；PROCESSING + 成功 → COMPLETED；PROCESSING + 失败 → FAILED。

状态机的价值是集中管理状态转换，拦截非法跳转，避免 if/elif 分散在各处。

小奕的 DocumentStatus 有 PENDING、PROCESSING、COMPLETED、FAILED、DELETED，但当前代码主要是状态字段和业务更新，不是一个独立的通用状态机框架。

## 8. 单 Agent 和多 Agent

单 Agent：一个模型负责理解问题、决定工具、读取结果和继续循环。

多 Agent：多个有不同角色或职责的 Agent 协作，例如：

1. Planner 负责拆解任务。
2. Retriever 负责检索。
3. Coder 负责写代码。
4. Reviewer 负责审核。

多 Agent 的代价是通信、状态同步、延迟、成本和错误传播增加。

小奕是单 Agent + 多工具：只有一个主要 LLM 循环，工具包括 textbook_search 和 calculator。

不要把多个工具叫成多个 Agent。工具是被 Agent 调用的函数，Agent 通常有自己的决策和上下文。

## 9. MCP

MCP 是 Model Context Protocol，用标准协议连接 AI Host 与外部工具和数据服务。

角色：

1. Host：AI 应用。
2. Client：Host 内部的 MCP 通信端。
3. Server：暴露能力的一方。

能力：

1. Tools：可执行动作。
2. Resources：可读取的数据。
3. Prompts：可复用的提示模板。

小奕当前把 TOOLS schema 传给 DeepSeek，再由 agent_tool.py 直接调用本地 Python 函数；没有 MCP Client、MCP Server 或 MCP 协议调用。

区别：MCP 解决工具和数据如何标准化连接，LangGraph 解决 Agent 流程如何组织。

## 10. Redis

Redis 是内存优先的 key-value 数据库，常用于：

1. 缓存。
2. Session 和 token 状态。
3. 限流计数。
4. 分布式锁。
5. 任务队列。

常见类型：String、Hash、List、Set、Sorted Set、Stream。

小奕代码事实：requirements.txt 中有 redis 依赖，但没有找到 Redis 客户端初始化、连接和读写；README 中是规划项，当前业务代码没有实际使用 Redis。

## 11. Agent Harness

Harness 是包在 LLM 外面的运行支架，把一次模型调用变成可执行、可控制、可记录的 Agent 运行。

通常包含：

1. Agent loop。
2. Tool dispatch。
3. Memory 和上下文管理。
4. 权限和安全边界。
5. 重试、超时和终止条件。
6. 日志、追踪和评测。

小奕没有一个叫 Harness 的类，但 agent_service.py、agent_tool.py、memory_service.py 和 chat_service.py 合起来体现了一个手写 Agent harness：拼上下文、调用模型、执行工具、回喂结果、限制轮数、返回结果并落库。

## 12. 最后十句速记

1. Q 查什么，K 能否匹配，V 拿什么。
2. 除以 sqrt(d_k) 是控制点积尺度，防止 softmax 饱和。
3. 多头是在多个表示子空间并行学习不同关系。
4. Transformer 由注意力、前馈网络、残差和归一化等模块堆叠而成。
5. MiniLM 在小奕里做 Embedding，DeepSeek 做生成和工具决策。
6. LangChain 是 LLM 应用组件抽象，LangGraph 是状态图和流程编排。
7. 状态机是状态、事件和合法转换规则。
8. 小奕是单 Agent + 多工具，不是多 Agent。
9. MCP 是外部工具和数据的标准连接协议。
10. Redis 当前只在依赖中出现，项目没有真正接入。
