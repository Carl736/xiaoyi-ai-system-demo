# app/service/textbook_tool.py
from typing import Optional,List
from app.utils.embedding import get_embedding
from app.vectorstore.faiss_db import vector_store
from sqlalchemy.ext.asyncio import AsyncSession
from app.service.document_service import get_user_documents_by_document_ids
SIMILARITY_THRESHOLD=0.7

async def textbook_search(
        question:str,
        user_id:int,
        db:AsyncSession,
        document_ids:Optional[List[str]]=None,
        top_k:int=3,
):
    """
        教材检索工具

        功能：
        0.权限验证
        1. 将用户问题转换为向量
        2. 从 FAISS 中搜索相似教材内容
        3. 根据 user_id 和 document_ids 进行过滤
        4. 返回教材片段
        """

    #权限验证
    if document_ids:
        #从Postsql中查询用户真正需要的教材
        documents=await get_user_documents_by_document_ids(
            db=db,
            user_id=user_id,
            document_ids=document_ids,
        )

        found_ids={
            document.document_id
            for document in documents
        }
        #用户请求访问的教材
        requested_ids=set(document_ids)

        #两者不一致，说明用户请求了没有权限访问的教材
        if found_ids!=requested_ids:
            unauthorized_ids=requested_ids-found_ids

            raise PermissionError(
                f"无权访问教材：{unauthorized_ids}"
            )
    #问题->向量
    query_vector=get_embedding(question)

    #2.FAISS检索
    docs=vector_store.search(
        query_vector=query_vector,
        top_k=top_k,
        user_id=user_id,
        document_ids=document_ids,
        threshold=SIMILARITY_THRESHOLD,
    )

    #3没找到
    if not docs:
        return []

    #整理Tool返回结果
    results=[]

    for doc in docs:
        results.append({
            "text":doc["text"],
            "page":doc["page"],
            "source":doc.get("source"),
            "document_id":doc.get("document_id"),
            "score":doc.get("score"),
        })

    return results
