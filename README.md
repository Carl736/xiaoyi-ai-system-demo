# 小奕 · 智能教学助手

基于用户自己上传的教材进行问答的 AI 教学助手。

## ✨ 项目特点
- **基于教材回答**：只从用户上传的 PDF 教材中检索相关内容，不胡说。
- **可溯源**：回答中会标注页码，方便回教材核对。
- **Agent 决策**：大模型自主判断是否需要检索教材或进行计算。

## 🛠️ 技术栈
- **后端**：FastAPI, SQLAlchemy (async), PostgreSQL, Redis
- **AI/RAG**：Sentence-Transformers, FAISS, DeepSeek API
- **Agent**：LLM Tool Calling, Conversation Memory

## 🚀 快速开始
1. 克隆仓库
2. 安装依赖：`pip install -r requirements.txt`
3. 配置数据库和 API Key
4. 运行：`uvicorn app.main:app --reload`

## 📁 项目结构
（这里可以简单列一下你的核心目录，比如 app/api, app/service, app/vectorstore 等）

## 📌 已实现功能
- 用户认证
- PDF 上传与解析
- RAG 问答（返回页码）
- Agent Tool Calling
- 聊天记录保存

## 📄 License
MIT