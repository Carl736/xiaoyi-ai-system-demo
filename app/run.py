import uvicorn
from app.core.logging_config import configure_logging

if __name__ == "__main__":
    configure_logging()
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)