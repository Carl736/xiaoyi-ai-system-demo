# pgvector、FAISS、Milvus 面试知识点

## 1. 三者分别是什么

1. PostgreSQL：关系型数据库，负责结构化数据、事务、用户、文档、chunk 和权限关系。
2. pgvector：PostgreSQL 的向量扩展，让 PostgreSQL 的表中可以存向量，并用 SQL 做向量相似度检索。
3. FAISS：向量检索库，负责在内存索引或文件索引中进行高效相似度搜索。
4. Milvus：独立的向量数据库服务，面向更大规模、分布式和生产化向量检索。

它们解决的是相近的问题，但部署形态和职责范围不同。

## 2. PostgreSQL + pgvector 的思路

chunk、user_id、document_id、page 和 embedding 可以放在同一张或相关的 PostgreSQL 表中。

检索时通过 SQL 进行：

1. user_id 过滤。
2. document_id 过滤。
3. 向量距离排序。
4. top_k 截取。

优点：

1. 少维护一个独立索引系统。
2. 结构化字段和向量可以在一次 SQL 查询中结合。
3. 事务、权限和向量数据更容易放在同一套数据库语义里。

代价：

1. 需要安装和维护 pgvector 扩展。
2. 向量检索性能和扩展方式受 PostgreSQL 体系影响。
3. 超大规模或高并发向量场景不一定适合只依赖一个关系库。

## 3. FAISS 的思路

FAISS 主要做向量索引和相似度搜索，不负责完整的关系型数据管理。

当前项目在 app/vectorstore/faiss_db.py 中使用：

1. IndexFlatIP 作为基础索引。
2. IndexIDMap 支持自定义向量 ID。
3. L2 归一化后用内积近似实现余弦相似度。
4. 通过 .faiss 文件和 metadata 文件保存索引。

PostgreSQL 仍然保存 Document 和 DocumentChunk 等业务数据，FAISS 单独保存向量索引和检索 metadata。

优点：

1. 接入简单。
2. 小规模数据使用 Flat 时结果精确。
3. 向量检索逻辑直接。
4. 不需要把向量检索设计成 SQL。

代价：

1. 业务数据和向量索引分开保存。
2. 需要自己维护 metadata 映射。
3. 需要自己处理索引保存、加载、删除和与 PostgreSQL 的一致性。
4. 单机文件索引不等于分布式向量数据库。

## 4. Milvus 的思路

Milvus 是独立部署的向量数据库服务，通常提供：

1. 向量存储。
2. 多种索引。
3. metadata 过滤。
4. 持久化。
5. 面向大规模数据的扩展能力。
6. 服务化和分布式部署能力。

优点：

1. 更适合大量向量和高并发检索。
2. 向量检索服务独立于业务数据库。
3. 有较完整的向量数据库能力。

代价：

1. 需要额外部署和运维服务。
2. 业务系统多一个网络依赖。
3. 小项目使用时部署复杂度更高。
4. 权限、文档关系和业务事务仍可能需要 PostgreSQL 配合。

## 5. 三者的核心取舍

1. PostgreSQL + pgvector：数据和向量放在一个数据库体系里，适合希望 SQL、事务、过滤和向量检索结合的场景。
2. FAISS：本地库或应用内索引，适合单机、规模较小、希望快速实现向量检索的场景。
3. Milvus：独立向量数据库，适合更大规模、更多并发和服务化部署的场景。

## 6. 当前项目能确认的事实

代码明确使用 PostgreSQL 保存业务数据，并使用 FAISS 保存向量索引。

相关文件：

1. app/db/database.py：PostgreSQL 连接。
2. app/model/document.py：Document 和 DocumentChunk 模型。
3. app/vectorstore/faiss_db.py：FAISS 索引、metadata、保存、加载和删除。
4. app/service/pdf_service.py：Embedding 写入 FAISS。
5. app/service/textbook_tool.py：调用 FAISS 检索。

当前代码中没有找到：

1. pgvector 的导入或向量列定义。
2. pgvector 距离查询。
3. Milvus 或 pymilvus 的导入和连接。

代码注释明确写到：项目数据规模较小，因此选择 Flat 以获得更精确的结果。

代码没有明确记录“为什么没有选择 pgvector”或“为什么没有选择 Milvus”的正式设计决策。因此不能把“作者一定认为 FAISS 比 pgvector 好”当成项目事实。

## 7. 面试回答时应该区分的事实和推理

可以确定地说：

1. 当前项目采用 PostgreSQL 加 FAISS。
2. PostgreSQL 保存业务实体和关系。
3. FAISS 负责向量相似度检索。
4. 当前 FAISS 是 IndexIDMap 包装 IndexFlatIP。
5. 当前代码没有 pgvector 和 Milvus。

只能作为架构取舍分析而说：

1. 如果想让结构化过滤和向量查询在同一 SQL 中完成，pgvector 更自然。
2. 如果数据规模很大、并发高、需要独立向量服务，Milvus 更合适。
3. 如果数据规模小、想快速实现精确向量搜索，FAISS 更简单。

这些是通用架构分析，不是当前项目代码明确写出的作者决策。
