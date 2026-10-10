"""阈值诊断：测所有教材类问题的 top-1 相似度，用数据定阈值"""
import json
from app.vectorstore.faiss_db import vector_store
from app.utils.embedding import batch_get_embeddings

vector_store.load("data/vectors/faiss_index")
print(f"索引向量数: {vector_store.index.ntotal}\n")

with open("app/eval/test_set.json", encoding="utf-8") as f:
    test_set = json.load(f)

targets = [it for it in test_set if it["expected_tool"] == "textbook_search"]

queries = []
for it in targets:
    q = it["question"]
    if it.get("context_turns"):  # 多轮题把上文拼上，近似 Agent 实际看到的
        q = "。".join(it["context_turns"]) + "。" + q
    queries.append(q)

vecs = batch_get_embeddings(queries)

print(f"{'id':<12}{'top1分数':<10}命中的chunk")
for it, v in zip(targets, vecs):
    res = vector_store.search(query_vector=v, top_k=3, user_id=1, threshold=None)
    if res:
        top = res[0]
        preview = top["text"][:28].replace("\n", " ")
        print(f"{it['id']:<12}{top['score']:.4f}    {preview}")
    else:
        print(f"{it['id']:<12}无结果")
