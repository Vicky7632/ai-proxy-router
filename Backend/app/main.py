from fastapi import FastAPI
from app.api.v1.chat import router as chat_router

app = FastAPI()
app.include_router(chat_router)

@app.get("/")
def root():
    return {"message": "AI proxy router running"}