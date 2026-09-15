#解析教材:解析的意思就是把教材的内容提取出来，变成我们可以使用的格式，比如文本、图片等。这样我们就可以对教材进行进一步的处理，比如分析、总结、生成问题等。然后我们就可以把这些处理后的内容存储起来，方便以后使用。总之，解析教材就是把教材的内容提取出来，变成我们可以使用的格式，这样我们就可以对教材进行进一步的处理和利用。
from pathlib import Path
from typing import Dict, List
from uuid import uuid4
from PyPDF2 import PdfReader
from app.utils.chunking import chunk_pages
from app.utils.embedding import get_embedding
from app.vectorstore.faiss_db import vector_store
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.document import DocumentStatus

from app.service.document_service import (
    create_document,
    update_document_status,
    save_document_chunks,
    update_chunk_vector_id
)
# =========================
# PDF 保存目录
# =========================
PDF_DIR = Path("data/pdfs")
PDF_DIR.mkdir(parents=True, exist_ok=True)#exist_ok=True表示如果目录已经存在，不会报错

# =========================
# 文本清洗
# =========================
def clean_text(text: str) -> str:
    if not text:
        return ""

    # 统一换行，统一文本中的换行符格式，把所有不同类型的换行符都转换成标准的 \n。
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # 去除连续空格
    lines = []
    #按行处理文本，去掉每行的首尾空格，并且只保留非空行
    for line in text.split("\n"):
        #去掉每行的首尾空格
        line = line.strip()

        if line:
            lines.append(line)

    return "\n".join(lines)#return "\n".join(lines)的意思是把列表 lines 中的每个元素用换行符 \n 连接起来，形成一个新的字符串，并返回这个字符串。也就是把处理后的每一行文本重新组合成一个完整的文本块，每行之间用换行符分隔。
# =========================
# PDF 解析
# =========================
def parse_pdf(file_path: str) -> List[Dict]:
    """
    解析 PDF。

    返回：

    [
        {
            "page": 1,
            "text": "第一页文本"
        },
        {
            "page": 2,
            "text": "第二页文本"
        }
    ]
    """

    reader = PdfReader(file_path)#file_path是pdf文件的路径，PdfReader是PyPDF2库中的一个类，用于读取和解析PDF文件。它会返回一个PdfReader对象，该对象包含了PDF文件的所有页面和相关信息。
#reader 接收的是一个 PdfReader 对象，它是 PyPDF2 库提供的一个类，用于读取和解析 PDF 文件。通过这个对象，我们可以访问 PDF 文件的各个页面，并提取文本内容。
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
    #enumerate(reader.pages, start=1) 是一个 Python 内置函数，用于遍历可迭代对象（这里是 reader.pages）并返回每个元素的索引和值。它会生成一个包含索引和值的元组序列，其中索引从 1 开始（因为我们指定了 start=1）.
    #该函数返回的就是一个列表 pages，其中每个元素都是一个字典，包含两个键值对：page 表示页码，text 表示该页的文本内容。
        try:
            text = page.extract_text() or ""#extract_text() 是 PyPDF2 库提供的一个方法，用于从 PDF 页面中提取文本内容。它会返回一个字符串，包含该页的所有文本。如果该页没有文本内容，则返回 None。为了避免 None 的情况，我们使用 or "" 来确保 text 至少是一个空字符串。
        except Exception as e:
            #except Exception as e意味着如果在尝试提取文本时发生任何异常（错误），程序不会崩溃，而是会捕获这个异常，并将其存储在变量 e 中。然后，程序会执行 except 块中的代码，这里是打印一条错误信息，说明第几页解析失败以及具体的错误原因。最后，将 text 设置为空字符串，以便继续处理下一页。
            print(f"第 {page_number} 页解析失败：{e}")
            text = ""

        text = clean_text(text)

        if not text:
            continue

        pages.append({
            "page": page_number,
            "text": text
        })

    return pages

#将上传的pdf保存到本地
def save_uploaded_pdf(
    file_bytes: bytes,#file_bytes 是一个字节串，表示上传的 PDF 文件的内容。它通常是从客户端上传的文件中读取的原始二进制数据。
    original_filename: str#original_filename 是上传的 PDF 文件的原始文件名，通常包含文件扩展名（例如 "document.pdf
) -> Path:
    """
    将上传的 PDF 保存到本地。

    使用 UUID 防止文件重名。
    """

    document_id = str(uuid4())#该函数生成一个唯一的 UUID（通用唯一识别码），并将其转换为字符串形式。UUID 是一种标准的标识符格式，通常用于确保在分布式系统中生成的 ID 是唯一的。在这里，document_id 用于为上传的 PDF 文件创建一个唯一的标识，以防止文件名冲突或覆盖。

    safe_filename = Path(original_filename).name#Path(original_filename).name 是 Python 的 pathlib 模块中的一个方法，用于获取文件路径的最后一部分，也就是文件名本身，而不包含目录路径。它会自动处理不同操作系统的路径分隔符，确保返回的文件名是安全的。

    if not safe_filename.lower().endswith(".pdf"):
        #如果 safe_filename 的小写形式不以 ".pdf" 结尾，则说明文件名没有正确的 PDF 扩展名。为了确保保存的文件具有正确的扩展名，我们在文件名后面添加 ".pdf"。这样可以避免用户上传的文件没有扩展名或使用了错误的扩展名，从而确保文件在保存后仍然被识别为 PDF 文件。
        safe_filename += ".pdf"

    file_path = PDF_DIR / f"{document_id}_{safe_filename}"

    with open(file_path, "wb") as f:
        #打开 file_path 指定的文件路径，以二进制写入模式 ("wb") 打开文件，并将文件对象赋值给变量 f。使用 with 语句可以确保在代码块执行完毕后，文件会被自动关闭，即使在写入过程中发生异常也会关闭文件，从而避免资源泄漏。
        f.write(file_bytes)

    return file_path

#这是一个完整的 PDF RAG 处理流程函数，它将上传的 PDF 文件进行解析、清洗、分块、生成 Embedding，并将结果存储到 FAISS 向量数据库中。函数接受三个参数：file_path（PDF 文件路径）、original_filename（原始文件名）和 user_id（用户 ID），并返回一个包含处理结果的字典。
async def process_pdf(
    file_path: str,
    original_filename: str,
    user_id: int,
    db:AsyncSession,
) -> Dict:
    """
        完整 PDF RAG 处理流程：

        PDF
          ↓
        Document
          ↓
        PDF 解析
          ↓
        文本分块
          ↓
        DocumentChunk
          ↓
        Embedding
          ↓
        FAISS
          ↓
        COMPLETED
        """
    from uuid import uuid4
    from app.service.document_service import (
        create_document,
        update_document_status,
        save_document_chunks,
        update_chunk_vector_id
    )

    from app.utils.embedding import batch_get_embeddings
    from app.vectorstore.faiss_db import vector_store

    # =========================
    # 1. 生成业务 document_id
    # =========================

    document_id=str(uuid4())

    # =========================
    # 2. 获取文件大小
    # =========================

    file_size=Path(file_path).stat().st_size

    # =========================
    # 3. 创建 Document
    # =========================

    document=await create_document(
        db=db,
        user_id=user_id,
        filename=original_filename,
        file_path=file_path,
        file_size=file_size,
        document_id=document_id,
    )

    try:
    # =========================
    # 4. 修改状态：PROCESSING
    # =========================
        await update_document_status(
            db=db,
            document_id=document_id,
            status=DocumentStatus.PROCESSING,
        )

    # =========================
    # 5. 解析 PDF
    # =========================
        pages=parse_pdf(file_path)

        if not pages:
            raise ValueError("PDF没有可解析的文本")
    # =========================
    # 6. PDF → chunks
    # =========================
        chunks=chunk_pages(pages)

        if not chunks:
            raise ValueError("pdf没有生成有效文本块")

    # =========================
    # 7. 保存 DocumentChunk
    # =========================
        chunk_objs=await save_document_chunks(
            db=db,
            document_id=document.id,
            chunks=chunks
        )
    # =========================
    # 8. 获取文本
    # =========================

        texts=[
            chunk_obj.content
            for chunk_obj in chunks
        ]

    # =========================
    # 9. Embedding
    # =========================

        embeddings=batch_get_embeddings(texts)

    # =========================
    # 10. 构造 FAISS metadata
    # =========================

        metadata=[]

        for chunk_obj in chunk_objs:

            metadata.append({
                "chunk_id":chunk_obj.id,
                "text":chunk_obj.content,
                "page":chunk_obj.page,
                "source":original_filename,
                "document_id":document_id,
                "user_id":user_id
            })
    # =========================
    # 11. 写入 FAISS
    # =========================

        vector_store.add(
            embeddings=embeddings,
            metadata=metadata
        )

    # =========================
    # 12. 保存 FAISS
    # =========================

        vector_store.save("data/vectors/faiss_index")

    # =========================
    # 13. 更新 vector_id
    # =========================

        for chunk_obj in chunk_objs:

            await update_chunk_vector_id(
                db=db,
                chunk_id=chunk_obj.id,
                vector_id=chunk_obj.id
            )

    # =========================
    # 14. 更新 Document
    # =========================

        await update_document_status(
            db=db,
            document_id=document.id,
            status=DocumentStatus.COMPLETED,
            total_pages=len(pages),
            total_chunks=len(chunk_objs),
        )

        return{
            "document_id":document_id,
            "filename":original_filename,
            "pages":len(pages),
            "chunks":len(chunk_objs),
            "status":"completed",
        }
    except Exception:
        # =========================
        # 失败 → FAILED
        # =========================
        await update_document_status(
            db=db,
            document_id=document.id,
            status=DocumentStatus.FAILED,
        )

        raise