# RAG 代码事实核对单

以下内容仅依据仓库当前代码记录；文件路径均相对于仓库根目录。

1. **PDF 解析用的库和大致流程**

   - 文件：`app/service/pdf_service.py`、`app/api/pdf.py`
   - 上传接口 `app/api/pdf.py::upload_pdf` 读取整个上传文件，检查扩展名、大小和空文件后，调用 `save_uploaded_pdf` 保存到 `data/pdfs`。
   - `app/service/pdf_service.py::parse_pdf` 使用 **PyPDF2** 的 `PdfReader` 打开文件，遍历 `reader.pages`，按从 1 开始的页号调用 `page.extract_text()`；随后用 `clean_text` 统一换行、去除每行首尾空白并丢弃空行。没有文本的页不加入结果。
   - `process_pdf` 的实际顺序是：创建 Document → 状态设为 PROCESSING → PDF 逐页解析 → 分页切分 → 保存 DocumentChunk → 批量 Embedding → 写入 FAISS → 保存 FAISS → 更新每个 chunk 的 `vector_id` → 状态设为 COMPLETED。异常时状态设为 FAILED。

2. **文本切分的 chunk 大小、overlap 具体数值**

   - 文件：`app/utils/chunking.py`、`app/service/pdf_service.py`
   - `chunk_text` 和 `chunk_pages` 的默认参数均为 `chunk_size=700`、`overlap=100`。
   - 单位按代码注释和实现是字符数：每个 chunk 取最多 700 个字符，相邻 chunk 从上一个结束位置回退 100 个字符开始。
   - `process_pdf` 调用 `chunk_pages(pages)`，未传入其他参数，因此实际使用上述默认值。切分按页分别进行，chunk 保留对应的 `page` 字段。

3. **Embedding 模型名称、向量维度、调用方式**

   - 文件：`app/core/model_loader.py`、`app/utils/embedding.py`、`app/vectorstore/faiss_db.py`
   - 模型通过 `sentence_transformers.SentenceTransformer` 加载，路径为 `C:\\Users\\Lenovo1\\paraphrase-multilingual-MiniLM-L12-v2`。
   - 文本调用 `model.encode(text).tolist()`；批量文本调用 `model.encode(texts).tolist()`。上传流程使用 `batch_get_embeddings(texts)`，查询流程使用 `get_embedding(question)`。
   - FAISS 向量维度代码设为 **384**（`FAISSVectorStore(dimension=384, ...)`）；输入维度不等于 384 时会抛出 `ValueError`。代码未另外调用远程 Embedding API。

4. **FAISS 索引具体类型和相似度度量方式**

   - 文件：`app/vectorstore/faiss_db.py`
   - `use_cosine=True` 时创建 `faiss.IndexFlatIP(384)`，再用 `faiss.IndexIDMap` 包装；全局 `vector_store` 也使用 `dimension=384, use_cosine=True`。
   - 添加和查询向量都会调用 `faiss.normalize_L2`。因此实际以归一化向量的内积作为相似度，代码将其作为余弦相似度使用。
   - 这是 Flat 精确搜索结构；代码中 `use_cosine=False` 的分支是 `IndexFlatL2`，但全局实例未使用该分支。

5. **相似度阈值、定义文件、过滤逻辑和 top_k**

   - 文件：`app/service/textbook_tool.py`、`app/vectorstore/faiss_db.py`、`app/service/agent_tool.py`
   - 默认阈值在 `app/service/textbook_tool.py` 定义为 `SIMILARITY_THRESHOLD=0.25`。教材检索函数默认 `top_k=3`、`threshold=0.25`，并将二者传入 `vector_store.search`。
   - `FAISSVectorStore.search` 先搜索；若指定 `user_id` 或 `document_ids`，内部搜索数量为 `min(max(top_k * 5, 20), index.ntotal)`，用于给过滤留余量。之后按得分和 ID 配对，跳过无效 ID、找不到 metadata 的 ID、用户不匹配的条目、文档不匹配的条目，以及 `score < threshold` 的条目。通过后加入结果，加入数量达到 `top_k` 即停止。
   - 因此通常返回最多 3 个结果；若调用者传入其他 `top_k`，则最多返回传入数量。阈值判断是“严格低于阈值过滤”，等于阈值不会被过滤。
   - 降级路径在 `app/service/agent_tool.py`：首次教材检索为空时将 `top_k` 乘 2，并把阈值设为 `DEGRADED_THRESHOLD=0.15` 后重查一次。代码中的说明文字写着“降至 0.5”，但实际常量和传参是 0.15。

6. **chunk 与 FAISS 向量 ID 的映射方式**

   - 文件：`app/service/pdf_service.py`、`app/vectorstore/faiss_db.py`、`app/model/document.py`
   - 每个 `DocumentChunk` 在数据库中的自增 `id` 被放入 FAISS metadata 的 `chunk_id` 字段。
   - `FAISSVectorStore.add` 将 `[m["chunk_id"] for m in metadata]` 转成 `int64` 数组，并通过 `IndexIDMap.add_with_ids(vectors, ids)` 写入 FAISS；因此 FAISS 自定义向量 ID 就是数据库 chunk 的 `id`。
   - 检索时先用 `metadata_map[chunk_id] = m` 建立 Python 字典，再用 FAISS 返回的 ID 查回 metadata。写入数据库的 `DocumentChunk.vector_id` 也被更新为同一个 `chunk_obj.id`。

7. **页码引用从哪里来，以及如何带到最终回答**

   - 文件：`app/service/pdf_service.py`、`app/utils/chunking.py`、`app/model/document.py`、`app/service/textbook_tool.py`、`app/service/agent_service.py`
   - 页码来源是 `parse_pdf` 遍历页面时的 `enumerate(..., start=1)` 生成的 `page_number`。该值进入页级字典的 `page` 字段，切分后复制到每个 chunk，并保存到数据库 `DocumentChunk.page`。
   - 建立 FAISS metadata 时把 `chunk_obj.page` 写入 metadata 的 `page` 字段；`textbook_search` 将检索项的 `page` 原样放入工具返回结果，同时返回 `text`、`source`、`document_id`、`score`。
   - Agent 将工具结果序列化为 tool message 交给 DeepSeek；`agent_service.py` 的系统提示要求回答教材问题时尽可能指出教材名称和页码、不得虚构页码。最终答案由 DeepSeek 生成，`chat_service.py` 取出 Agent 返回的 `answer` 对外返回。
   - 代码中未找到把页码在服务端单独格式化成固定引用字符串的逻辑；页码是通过 tool 结果交给模型生成最终回答。

8. **所有检索结果都低于阈值时的处理路径**

   - 文件：`app/vectorstore/faiss_db.py`、`app/service/textbook_tool.py`、`app/service/agent_tool.py`、`app/service/agent_service.py`
   - `search` 会跳过所有 `score < threshold` 的条目并返回空列表；`textbook_search` 对空结果直接返回 `[]`。
   - `execute_tool_resilient` 对教材工具的空列表执行一次降级重查：`top_k` 翻倍、阈值改为 0.15。若仍为空，返回 `success=True, degraded=True, results=[]`，并附带“教材中仍没有检索到相关内容”的提示。
   - 该工具结果随后作为 tool message 交给 Agent。系统提示要求模型明确告诉用户当前上传教材中没有检索到相关内容，不要编造教材来源；若工具调用/循环本身失败，代码还有对应的错误或超限回答路径。

9. **软删除实现、检索规避方式、是否需要重建索引**

   - 文件：`app/model/document.py`、`app/service/document_service.py`、`app/api/document.py`、`app/vectorstore/faiss_db.py`
   - 软删除标记是数据库 `Document.status = DocumentStatus.DELETED`，枚举值为 `"deleted"`。文档查询、列表和统计默认用 `status != DELETED` 过滤。
   - `soft_delete_document` 先取得该文档所有 chunk 的 `vector_id`，调用 `vector_store.delete_by_vector_ids`：FAISS 使用 `remove_ids` 删除向量，同时从 `metadata` 列表删除 `chunk_id` 匹配项；随后调用 `vector_store.save("data/vectors/faiss_index")` 持久化删除结果，最后把数据库文档状态设为 `DELETED`。
   - 因此被删内容靠“从 FAISS 向量和 metadata 中实际移除”避免再次被检索；数据库状态字段同时保留软删除记录。代码没有在删除后重建整个索引的步骤，使用的是按 ID 删除并保存现有索引。

