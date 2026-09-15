from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.service.user_service import get_current_user
from app.model.user import User

from app.service.pdf_service import (
    save_uploaded_pdf,
    process_pdf
)

#创建路由
router = APIRouter(
    prefix="/api/upload",#所有接口路径前面自动加上 /api/upload
    tags=["PDF"] # 在 Swagger 文档里归类为 "PDF" 组
)


# 最大上传文件大小：20MB
MAX_FILE_SIZE = 20 * 1024 * 1024


@router.post("/pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db:AsyncSession=Depends(get_db)
):
    """
    上传 PDF 并建立知识库。
    """

    # ==========================================
    # 1. 检查文件名
    # ==========================================

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="文件名不能为空"
        )

    suffix = Path(file.filename).suffix.lower()# 提取扩展名，如 ".pdf"，转小写

    if suffix != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="只允许上传 PDF 文件"
        )

    # ==========================================
    # 2. 读取文件
    # ==========================================

    file_bytes = await file.read()#异步读取·整个文件到内存

    # ==========================================
    # 3. 文件大小限制
    # ==========================================

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="PDF 文件不能超过 20MB"
        )

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="上传文件为空"
        )

    # ==========================================
    # 4. 保存 PDF
    # ==========================================

    try:

        file_path = save_uploaded_pdf(
            file_bytes=file_bytes,
            original_filename=file.filename
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"保存 PDF 失败：{str(e)}"
        )
#截止到此只是把文件拷贝到硬盘，还没开始解析
    # ==========================================
    # 5. 处理 PDF
    #
    # 创建 Document
    # ↓
    # PDF 解析
    # ↓
    # Chunk
    # ↓
    # DocumentChunk
    # ↓
    # 获取 DocumentChunk.id
    # ↓
    # Embedding
    # ↓
    # FAISS
    # ==========================================

    try:

        result = await process_pdf(
            db=db,
            file_path=str(file_path),
            original_filename=file.filename,
            user_id=user.id,
        )

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:

        print(f"PDF 处理失败：{e}")

        raise HTTPException(
            status_code=500,
            detail="PDF 处理失败，请检查服务器日志"
        )

    return {
        "message": "PDF 上传并处理成功",
        "data": result
    }