#新增的BM25和faiss联合检索，主要围绕关键词复现进行定位，
#两者是不同的评分系统，结合联合检索
#配合jieba把中文句子切成关键词、
from rank_bm25 import BM25Okapi
import jieba
from operator import itemgetter
from typing import Dict,List,Optional
class BM25Store:
    def __init__(self):
        self.metadata=[]
        self.tokenized_corpus=[]
        self.bm25=None

    def build(self,metadata:list[dict]):
        if not metadata:
            return
        self.metadata=metadata
        self.tokenized_corpus=[]
        for m in metadata:
            self.tokenized_corpus.append(jieba.lcut(m["text"]))#self.tokenized_corpus[0] ↔ self.metadata[0]
        self.bm25=BM25Okapi(self.tokenized_corpus)#根据这些分词结果建立BM25索引


    def search(self,
               question:str,
               user_id:Optional[int]=None,
               document_ids:Optional[List[str]]=None,
               top_k:int=3,
               ):
        if self.bm25 is None:
            return []

        if not question:
            return []

        que_tokens=jieba.lcut(question)
        scores=self.bm25.get_scores(que_tokens)
        index_scores=[]
        for index,score in enumerate(scores):
            if score<=0:
                continue
            if user_id is not None:
                if self.metadata[index].get("user_id")!=user_id:
                    continue#用户隔离
            if document_ids is not None:
                if self.metadata[index].get("document_id") not in document_ids:
                    continue#文档过滤

            index_scores.append((index,score))
        index_scores.sort(key=itemgetter(1),reverse=True)#取每个元组第二个值，reverse：从大到小排列
        top_items=index_scores[:top_k]

        result=[]
        for index,score in top_items:
            item=dict(self.metadata[index])
            item["score"]=float(score)
            result.append(item)
        return result

bm25_store=BM25Store()

def rrf_fuse(
        vector_results:list[dict],
        bm25_results:list[dict],
        top_k,
):
    # chunk_dict的结构可以理解成：
    # {
    #     chunk_id: {
    #         "item": 原始结果字典,
    #         "rrf_score": 累积融合分数,
    #     }
    # }
    # vector_results = [
    #     {
    #         "chunk_id": 12,
    #         "text": "牛顿第一定律说明物体具有惯性。",
    #         "page": 1,
    #         "source": "物理教材.pdf",
    #         "document_id": "book-1",
    #         "user_id": 3,
    #         "score": 0.86,
    #     },]
    # bm25_results = [
    #     {
    #         "chunk_id": 18,
    #         "text": "牛顿第二定律描述力和加速度。",
    #         "page": 3,
    #         "source": "物理教材.pdf",
    #         "document_id": "book-1",
    #         "user_id": 3,
    #         "score": 2.4,
    #     },]
    chunk_dict={}
    for index,value in enumerate(vector_results,start=1):
        chunk_id=value.get("chunk_id")
        rrf_score=1/(60+index)
        if chunk_id not in chunk_dict:
            chunk_dict[chunk_id]={
                "item":value,
                "rrf_score":rrf_score
            }
            continue
        chunk_dict[chunk_id]["rrf_score"]+=rrf_score#已经出现就累加
    for rank,value in enumerate(bm25_results,start=1):
        chunk_id=value.get("chunk_id")
        rrf_score=1/(60+rank)
        if chunk_id not in chunk_dict:
            chunk_dict[chunk_id]={
                "item":value,
                "rrf_score":rrf_score
            }
            continue
        chunk_dict[chunk_id]["rrf_score"]+=rrf_score#
    # [
    #     {
    #         "item": {"chunk_id": 12, "text": "..."},
    #         "rrf_score": 0.032,
    #     },
    #     {
    #         "item": {"chunk_id": 18, "text": "..."},
    #         "rrf_score": 0.016,
    #     },
    # ]
    fused_items=list(chunk_dict.values())

    fused_items.sort(key=itemgetter("rrf_score"),reverse=True)
    toop_items=fused_items[:top_k]
    results=[]

    for entry in toop_items:
        item=dict(entry["item"])
        item["rrf_score"]=entry["rrf_score"]
        results.append(item)
    return results
