from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.chat import router as chat_router
from app.config import settings
from app.routes.auth import router as auth_router
from app.routes.keys import router as keys_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(auth_router)
app.include_router(keys_router)
app.include_router(chat_router)

@app.get("/")
def root():
    return {"message": "AI proxy router running"}