"""阈值扫描：看每个阈值下，真题正确chunk存活几个、防幻觉题几个返回空"""
import json
from app.vectorstore.faiss_db import vector_store
from app.utils.embedding import batch_get_embeddings

vector_store.load("data/vectors/faiss_index")

with open("app/eval/test_set.json", encoding="utf-8") as f:
    test_set = json.load(f)

# 答案 key：每道真题正确内容在第几章（按我写的教材）
ANSWER_KEY = {
    "single_01": "第一章", "single_02": "第二章", "single_03": "第一章",
    "single_04": "第一章", "single_05": "第一章", "single_06": "第二章",
    "single_07": "第二章", "single_08": "第三章", "single_09": "第一章",
    "single_10": "第二章", "multi_01": "第二章", "multi_02": "第一章",
    "multi_03": "第二章", "multi_04": "第二章", "multi_05": "第一章",
    "multi_06": "第三章", "turn_01": "第一章", "turn_02": "第二章",
    "turn_03": "第一章", "turn_04": "第三章",
}
HALLU = ["hallu_01", "hallu_02", "hallu_03"]

targets = [it for it in test_set if it["expected_tool"] == "textbook_search"]
queries = []
for it in targets:
    q = it["question"]
    if it.get("context_turns"):
        q = "。".join(it["context_turns"]) + "。" + q
    queries.append(q)

vecs = batch_get_embeddings(queries)
rows = []
for it, v in zip(targets, vecs):
    res = vector_store.search(query_vector=v, top_k=3, user_id=1, threshold=None)
    scores = {"第一章": 0, "第二章": 0, "第三章": 0}
    for r in res:
        for ch in scores:
            if ch in r["text"][:20]:
                scores[ch] = r["score"]
    rows.append((it["id"], scores))

print(f"{'id':<12}{'第一章':<8}{'第二章':<8}{'第三章':<8}")
for qid, s in rows:
    print(f"{qid:<12}{s['第一章']:.4f}  {s['第二章']:.4f}  {s['第三章']:.4f}")

print("\n阈值扫描：")
for th in [0.2, 0.25, 0.3, 0.35, 0.4, 0.5]:
    keep = sum(1 for qid, s in rows if qid in ANSWER_KEY and s[ANSWER_KEY[qid]] >= th)
    empty = sum(1 for qid, s in rows if qid in HALLU and max(s.values()) < th)
    print(f"  阈值 {th}: 真题正确chunk存活 {keep}/20，防幻觉题返回空 {empty}/3")
