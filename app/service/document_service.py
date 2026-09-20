# app/service/document_service.py

from typing import List, Optional, Dict, Any

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.document import (
    Document,
    DocumentChunk,
    DocumentStatus,
)

async def create_document(
        db:AsyncSession,
        user_id:int,
        filename:str,
        file_path:str,
        file_size:int,
        document_id:str,
)->Document:
    """创建文档记录"""
    #创建时完善的信息是那些固定的不会再变的数据，比如id，name，path等，像total_pages，total_chunks，status等是会随着文档处理的进度而变化的，所以不在创建时设置
    #会放到update_document_status中去更新，两个函数组合完善Document的所有信息
    doc=Document(
        user_id=user_id,
        filename=filename,
        filepath=file_path,
        file_size=file_size,
        document_id=document_id,
        status=DocumentStatus.PENDING#PENDING表示文档待处理,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc

async def update_document_status(
        db:AsyncSession,
        document_id:int,
        status:DocumentStatus,
        total_pages:Optional[int]=None,
        total_chunks:Optional[int]=None
):
    """更新文档状态"""
    stmt=(
        update(Document).where(Document.id==document_id).values(
            status=status,
            total_pages=total_pages,
            total_chunks=total_chunks
        )
    )
    await db.execute(stmt)
    await db.commit()


#保存chunk到PostgreSQL
async def save_document_chunks(
        db:AsyncSession,
        document_id:int,
        chunks:List[Dict[str, Any]],
)->List[DocumentChunk]:
    """
    将 PDF 分块保存到 PostgreSQL。

    chunks 示例：

    [
        {
            "page": 1,
            "text": "这是第一段"
        },
        {
            "page": 1,
            "text": "这是第二段"
        },
        {
            "page": 2,
            "text": "这是第三段"
        }
    ]
    """
    chunk_objs=[]
    #enumerate会给每个chunk分配一个从0开始的序号，由idx接收
    for idx,chunk in enumerate(chunks):
        #先创建Chunk记录，暂时不知道FAISS里的位置，zip函数将chunks打包成一个个元组，idx是索引，chunk是文档块
        chunk_obj=DocumentChunk(
            document_id=document_id,
            chunk_index=idx,#chunk在当前文档中的数据
            page=chunk["page"],#第几页
            content=chunk["text"],#该分块的内容
            vector_id=None,#是FAISS索引中这个向量被分配到的位置序号，稍后更新
                           #当以后要删除一本书，需要知道这本书所有chunk在FAISS中的位置编号才能去删
                           #目前数据还没进FAISS，所没有索引
        )
        db.add(chunk_obj)
        chunk_objs.append(chunk_obj)
    await db.commit()

    #刷新每个chunk，获取它们的id
    for chunk_obj in chunk_objs:
        await db.refresh(chunk_obj)

    #现在可以更新vector_id
    return chunk_objs

async def update_chunk_vector_id(
        db:AsyncSession,
        chunk_id:int,
        vector_id:int,
):
    """
    更新chunk对应的FAISS ID
    """
    stmt=(
        update(DocumentChunk)
        .where(DocumentChunk.id==chunk_id)
        .values(vector_id=vector_id)
    )

    await db.execute(stmt)

    await db.commit()

#这个函数的意思是获取当前用户的所有教材列表
async def get_user_documents(
        db:AsyncSession,
        user_id:int,
        include_deleted:bool=False,#是否在被删除之内
)->List[Document]:
    stmt=select(Document).where(
        Document.user_id==user_id
    )

    if not include_deleted:
        stmt=stmt.where(
            Document.status!=DocumentStatus.DELETED
        )
    stmt=stmt.order_by(Document.created_at.desc())#最新的教材排到最前面

    result=await db.execute(stmt)

    return result.scalars().all()

async def get_document_by_id(
        db:AsyncSession,
        document_id:int,
        user_id:int,
)->Optional[Document]:
    stmt=select(Document).where(
        Document.id==document_id,
        Document.user_id==user_id,
        Document.status!=DocumentStatus.DELETED,
    )

    result=await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_document_by_document_id(
        db:AsyncSession,
        user_id:int,
        document_uuid:str,
)->Optional[Document]:
    stmt=select(Document).where(
        user_id==Document.user_id,
        Document.document_id==document_uuid,
        Document.status!=DocumentStatus.DELETED
    )

    result=await db.execute(stmt)

    return result.scalar_one_or_none()

async def soft_delete_document(
        db:AsyncSession,
        document_id:int,
        user_id:int,
)->bool:
    """
    删除文档：

    1. 检查文档是否属于当前用户
    2. 查询文档对应的所有 chunks
    3. 获取这些 chunk 对应的 FAISS ID
    4. 从 FAISS 删除向量
    5. 删除 FAISS metadata
    6. 保存 FAISS
    7. PostgreSQL 中将文档标记为 DELETED
    """

    #1.查询文档
    doc=await get_document_by_id(
        db,
        document_id,
        user_id,
    )
    if not doc:
        return False

    #2.查询这个文档的所有chunks
    chunks=await get_document_chunks(
        db=db,
        document_id=document_id,
    )

    #3.获取FAISS vector_id
    vector_ids=[]

    for chunk in chunks:
        if chunk.vector_id is not None:
            vector_ids.append(chunk.vector_id)
    print(
        f"准备删除文档：{doc.filename}，"
        f"chunks={len(chunks)}，"
        f"FAISS vectors={len(vector_ids)}"
    )

    #4.准备删除FAISS向量
    if vector_ids:
        from app.vectorstore.faiss_db import vector_store

        vector_store.delete_by_vector_ids(vector_ids)

        #5.保存FAISS
        vector_store.save(
            "data/vectors/faiss_index"
        )

    #6.PostgreSql软删除
    doc.status=DocumentStatus.DELETED
    await db.commit()
    return True

async def get_document_chunks(
    db: AsyncSession,
    document_id: int,
) -> List[DocumentChunk]:

    stmt = (
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id == document_id
        )
        .order_by(
            DocumentChunk.chunk_index#index是文档内部顺序
        )
    )

    result = await db.execute(stmt)

    return result.scalars().all()

#统计当前用户上传了多少本教材，总共有多少个chunk
async def get_document_stats(
        db:AsyncSession,
        user_id:int
)->Dict[str,Any]:

    total_stmt=select(
        func.count()#SQL中的count* 用来计数
    ).select_from(
        Document
    ).where(
        Document.user_id==user_id,
        Document.status!=DocumentStatus.DELETED,
    )
    total_result=await db.execute(total_stmt)
    total_docs=total_result.scalar() or 0

    chunk_stmt=select(
        func.sum(Document.total_chunks)
    ).where(
        Document.user_id==user_id,
        Document.status!=DocumentStatus.DELETED,
    )
    chunk_result=await db.execute(chunk_stmt)

    total_chunks=chunk_result.scalar() or 0

    return{
        "total_documents":total_docs,
        "total_chunks":total_chunks,
    }

async def get_user_documents_by_document_ids(
    db: AsyncSession,
    user_id: int,
    document_ids: List[str],
) -> List[Document]:
    """
    根据 document_id 查询当前用户拥有的教材。

    只返回：
    1. 属于当前用户的文档
    2. document_id 在请求列表中的文档
    3. 没有被软删除的文档
    """

    stmt = (
        select(Document)
        .where(
            Document.user_id == user_id,
            Document.document_id.in_(document_ids),
            Document.status != DocumentStatus.DELETED,
        )
    )

    result = await db.execute(stmt)

    return list(result.scalars().all())



