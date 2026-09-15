from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.vectorstore.faiss_db import vector_store

from app.api import chat, user, pdf, document


app = FastAPI(
    title="小奕 AI System",
    description="小奕 AI 智能教学助手",
    version="1.0.0",
)


# ==========================================
# 注册路由
# ==========================================

app.include_router(chat.router)

app.include_router(user.router)

app.include_router(pdf.router)

app.include_router(document.router)


# ==========================================
# 静态文件
# ==========================================

BASE_DIR = Path(__file__).resolve().parent

app.mount(
    "/static",
    StaticFiles(
        directory=BASE_DIR / "static"
    ),
    name="static"
)


# ==========================================
# 根路径
# ==========================================

@app.get("/")
async def root():
    return {
        "msg": "小奕启动成功"
    }


# ==========================================
# 启动事件
# ==========================================

@app.on_event("startup")
async def startup_event():

    vector_store.load(
        "data/vectors/faiss_index"
    )

    print("FAISS 向量库加载成功")