from fastapi import FastAPI
from app.api.v1.chat import router as chat_router
from app.routes.auth import router as auth_router

app = FastAPI()
app.include_router(auth_router)
app.include_router(chat_router)

@app.get("/")
def root():
    return {"message": "AI proxy router running"}