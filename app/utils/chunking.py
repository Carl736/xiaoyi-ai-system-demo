from typing import List, Dict

#单页文本切分
def chunk_text(
    text: str,
    chunk_size: int = 700,#默认
    overlap: int = 100
) -> List[str]: # ← 返回值注解：返回一个字符串列表
    """
    将一段文本切分成多个 chunk。

    参数：
        text: 原始文本
        chunk_size: 每个 chunk 最大字符数
        overlap: 相邻 chunk 重叠字符数

    返回：
        chunk 列表
    """

    if not text:
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")

    if overlap < 0:
        raise ValueError("overlap 不能小于 0")

    if overlap >= chunk_size:
        raise ValueError("overlap 必须小于 chunk_size")

    text = text.strip()#去掉字符串开头和结尾的空白字符

    if not text:
        return []

    chunks = []

    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)

        chunk = text[start:end].strip()#将text的从start到end的子字符串去掉首尾空格后赋值给chunk

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        start = end - overlap

    return chunks

#多页文本切分
def chunk_pages(
    pages: List[Dict],#list里面的dict，dict里面有两个键值对，一个是page：1，一个是text：第一页的内容
    chunk_size: int = 700,
    overlap: int = 100
) -> List[Dict]:
    """
    对 PDF 的每一页分别进行分块。

    pages 格式：

    [
        {
            "page": 1,
            "text": "第一页内容"
        },
        {
            "page": 2,
            "text": "第二页内容"
        }
    ]

    返回：

    [
        {
            "page": 1,
            "text": "...",
        },
        ...
    ]
    """

    all_chunks = []

    for page_data in pages:

        page_number = page_data["page"]
        text = page_data["text"]

        chunks = chunk_text(
            text=text,
            chunk_size=chunk_size,
            overlap=overlap
        )

        for chunk in chunks:
            all_chunks.append({
                "page": page_number,
                "text": chunk
            })

    return all_chunks