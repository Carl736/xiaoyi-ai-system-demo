# LangGraph 与 MCP 面试概念清单

## 1. 一句话区分

1. LangGraph：在应用内部编排 Agent 状态和执行流程。
2. MCP：用统一协议连接 AI 应用与外部工具、数据服务。

记忆：LangGraph 管流程怎么走，MCP 管工具和数据怎么接。

代码核对：requirements.txt 虽然列有 LangGraph 和 LangChain 依赖，但 app 代码没有找到 LangGraph API 的导入或调用，也没有找到 MCP SDK、MCP Client/Server 或协议调用。依赖存在不等于运行代码使用了它。

## 2. LangGraph 核心概念

LangGraph 把 Agent 工作流表示成图，核心是 State、Node、Edge。

1. State：流程共享的数据快照，例如 question、messages、检索结果、iteration、answer。节点读取状态并返回更新。
2. Node：执行某项工作的函数，例如调用 LLM、运行工具或检索知识库。
3. Edge：决定节点执行后下一步去哪。普通边固定跳转，条件边按状态或模型结果分支。

示例流程：LLM 节点有 tool_call 时走工具节点；没有 tool_call 时结束；工具节点完成后回到 LLM 节点。

一般要定义状态、节点和边，compile 成可执行图，然后 invoke 或 stream。LangGraph 可提供 checkpoint 等状态保存能力，但应用需要配置和使用。

## 3. LangGraph 对照小奕

小奕没有 LangGraph API，但手写循环可做概念映射：

1. messages、question、iteration：类似 State。
2. 调用 DeepSeek：类似 LLM Node。
3. execute_tool_resilient：类似 Tool Node。
4. 检查是否有 tool_call 的 if：类似 Conditional Edge。
5. 工具结果追加 messages 后继续 for 循环：类似工具节点回到 LLM 节点。
6. 没有工具调用后 yield done：类似到达 END。
7. max_iteration：代码侧的循环上限。

这是概念映射，不代表项目实际使用 LangGraph。LangGraph 的价值是显式组织状态、分支和循环，并为复杂工作流提供状态管理能力。它不自动保证回答正确，也不代替业务规则和权限设计。

LangGraph 不等于多 Agent；单 Agent 的分支和循环也能用图表达。

## 4. MCP 是什么

MCP 全称 Model Context Protocol，是 AI 应用连接外部工具和数据源的标准化协议。

1. Host：AI 应用或 Agent 产品。
2. Client：运行在 Host 中，负责讲 MCP 协议并连接 Server。
3. Server：向 Client 暴露工具、资源或 prompt。

关系：AI Host/Agent → MCP Client → MCP Server → 工具、数据库、文件或外部服务。

通常模型在 Host 中决定是否使用工具。MCP Server 提供能力，不一定直接和模型对话。

## 5. MCP 的三类能力

1. Tools：可执行动作，例如计算、查询数据库、教材搜索、调用 API。通常有名称、描述、输入 schema 和执行结果。
2. Resources：供应用读取并放进上下文的数据，例如文件内容或数据库记录，通常由应用决定读取什么。
3. Prompts：可复用的提示模板，通常由用户或应用选择并填入参数。

简记：Tools 让模型采取动作，Resources 提供上下文，Prompts 提供模板。

## 6. MCP 工具调用大致流程

1. MCP Client 连接 MCP Server。
2. Client 查询 Server 暴露的能力，例如 tools 列表。
3. Host 将可用工具信息提供给模型。
4. 模型选择工具并生成参数。
5. MCP Client 通过协议请求 Server 执行。
6. Server 返回结果，Host 再把结果交给模型。

MCP 统一能力发现和调用的协议格式，具体工具业务仍由 Server 实现。传输方式需按实际 SDK 和部署确认。

## 7. MCP 对照小奕

当前小奕链路：agent_service.py 将 TOOLS schema 传给 DeepSeek；模型返回 tool_call；agent_tool.py 按名称分发；textbook_tool.py 或 calculator_tool.py 执行；结果加入 messages。

概念上，工具 schema 类似工具描述，名称分发类似本地调度，两个工具模块是具体实现，工具结果回到模型上下文。

但当前代码没有 MCP Client/Server，也没有 MCP 协议调用。它是应用内部 Python 函数直接分发，不是 MCP。

## 8. LangGraph 和 MCP 可组合

它们不是替代关系：LangGraph 组织模型节点、工具节点和循环；MCP Client 可以作为工具节点内部的调用方式，去请求 MCP Server。也可以像小奕当前实现一样，两者都不用，手写循环并调用本地函数。

## 9. 面试容易混淆的点

1. LangGraph 是工作流编排框架；MCP 是外部能力连接协议。
2. State、Node、Edge 是 LangGraph 流程概念；Host、Client、Server 是 MCP 架构角色。
3. MCP 不等于工具本身；它规定能力如何发现和调用。
4. 模型返回 tool_call JSON 不等于 MCP 调用；应用可以收到 function call 后直接执行本地函数。
5. requirements.txt 声明依赖不证明项目实际使用，需查导入、初始化和调用。

## 10. 结合小奕的回答要点

1. 项目是单 Agent，循环由 Python 异步 for 手写。
2. 模型每轮返回普通内容或 tool_call。
3. Python 按工具名分发到本地函数。
4. 工具结果追加进 messages，再进行下一轮模型调用。
5. 流程概念上类似 State、Node、条件边，但项目没有 LangGraph API 实现。
6. 项目没有 MCP Client/Server，工具通过内部函数调用。
7. LangGraph 解决流程编排，MCP 解决外部工具和数据的标准化连接。

## 11. 代码核对位置

1. app/service/agent_service.py：Agent 循环、模型调用、tool_call 分支。
2. app/service/agent_tool.py：工具 schema、注册和分发。
3. app/service/textbook_tool.py：教材检索工具。
4. app/service/calculator_tool.py：计算器工具。
5. requirements.txt：列有 LangGraph、LangChain 相关依赖。

## 12. 官方参考

1. [LangGraph Graph API 概念](https://langchain-ai.github.io/langgraph/concepts/low_level/)
2. [LangGraph 官方概览](https://langchain-ai.github.io/langgraph/)
3. [MCP Python SDK 官方入门](https://py.sdk.modelcontextprotocol.io/get-started/first-steps/)
