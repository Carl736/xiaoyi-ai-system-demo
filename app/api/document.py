# app/api/document.py

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.model.user import User
from app.service.user_service import get_current_user

from app.service.document_service import (
    get_user_documents,
    get_document_by_id,
    get_document_chunks,
    get_document_stats,
    soft_delete_document,
)


router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"]
)


# =========================================================
# 1. 获取当前用户所有文档
# =========================================================

@router.get("")
async def list_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户的所有教材。
    """

    documents = await get_user_documents(
        db=db,
        user_id=user.id,
    )

    return {
        "total": len(documents),

        "documents": [
            {
                "id": doc.id,
                "document_id": doc.document_id,
                "filename": doc.filename,
                "file_size": doc.file_size,
                "status": doc.status.value,
                "total_pages": doc.total_pages,
                "total_chunks": doc.total_chunks,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
            }
            for doc in documents
        ]
    }


# =========================================================
# 2. 获取统计信息
# =========================================================

@router.get("/stats/overview")
async def document_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户知识库统计。
    """

    return await get_document_stats(
        db=db,
        user_id=user.id,
    )


# =========================================================
# 3. 获取某个文档详情
# =========================================================

@router.get("/{document_id}")
async def document_stats(
        document_id: int,
        user:User=Depends(get_current_user),
        db:AsyncSession=Depends(get_db),
):
    """
       获取某个教材的详细信息，包括 Chunk。
       """
    doc =  await get_document_by_id(
        db=db,
        document_id=document_id,
        user_id=user.id,
    )

    if not doc:

        raise HTTPException(
            status_code=404,
            detail="文档不存在",
        )

    chunks=await get_document_chunks(
        db=db,
        document_id=document_id,
    )

    return{
        "document":{
            "id":doc.id,
            "document_id":doc.document_id,
            "filename":doc.filename,
            "filepath":doc.filepath,
            "file_size":doc.file_size,
            "status":doc.status.value,
            "total_pages":doc.total_pages,
            "total_chunks":doc.total_chunks,
            "created_at":doc.created_at,
            "update_at":doc.updated_at,
        },
        "chunks":[
            {
                "id":chunk.id,
                "chunk_index":chunk.chunk_index,
                "page":chunk.page,
                "content":chunk.content,
                "vector_id":chunk.vector_id,
                "created_at":chunk.created_at,
            }
            for chunk in chunks
        ]

    }


# =========================================================
# 4. 删除文档
# =========================================================

@router.delete("/{document_id}")
async def delete_document(
        document_id:int,
        user:User=Depends(get_current_user),
        db:AsyncSession=Depends(get_db),
):
    """
    软删除文档。

    注意：
    当前这里只删除 PostgreSQL 中的 Document 状态。
    FAISS 向量删除需要单独处理。
    """
    success=await soft_delete_document(
        db=db,
        document_id=document_id,
        user_id=user.id,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="文档不存在",
        )

    return {
        "message":"文档删除成功"
    }
