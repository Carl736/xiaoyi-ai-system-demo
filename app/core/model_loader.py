from sentence_transformers import SentenceTransformer

#加载一个预训练模型，将过来的文本转化为向量
model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)