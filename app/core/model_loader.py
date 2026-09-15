from sentence_transformers import SentenceTransformer

#加载一个预训练模型，将过来的文本转化为向量
model = SentenceTransformer(
    r"C:\Users\Lenovo1\paraphrase-multilingual-MiniLM-L12-v2"
)