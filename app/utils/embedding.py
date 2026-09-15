#文本转化为向量的工具函数

from app.core.model_loader import model


# 单文本 embedding：调用core的预训练模型，将文本转化为向量
def get_embedding(text: str):
    return model.encode(text).tolist()

# 批量 embedding
def batch_get_embeddings(texts: list[str]):
    return model.encode(texts).tolist()