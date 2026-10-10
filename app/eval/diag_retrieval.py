"""检索链路诊断：自底向上逐层验证"""
from app.vectorstore.faiss_db import vector_store
from app.utils.embedding import get_embedding

print("=== 1. 加载索引 ===")
vector_store.load("data/vectors/faiss_index")
print("ntotal:", vector_store.index.ntotal)
print("metadata 条数:", len(vector_store.metadata))
if vector_store.metadata:
    m0 = vector_store.metadata[0]
    print("keys:", list(m0.keys()))
    print("user_id:", m0.get("user_id"), "| chunk_id:", m0.get("chunk_id"))
    print("text前60字:", m0.get("text", "")[:60])

print("=== 2. 无阈值检索（看原始相似度）===")
q = get_embedding("牛顿-莱布尼茨公式是什么")
res = vector_store.search(query_vector=q, top_k=3, user_id=1, threshold=None)
print("命中数:", len(res))
for r in res:
    print(f"  score={r['score']:.4f} | user_id={r.get('user_id')} | {r['text'][:40]}")

print("=== 3. 阈值0.7检索 ===")
res2 = vector_store.search(query_vector=q, top_k=3, user_id=1, threshold=0.7)
print("命中数:", len(res2))
