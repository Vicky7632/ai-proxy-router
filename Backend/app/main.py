import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.analytics import router as analytics_router
from app.api.v1.chat import router as chat_router
from app.api.v1.providers import router as providers_router
from app.config import settings
from app.routes.auth import router as auth_router
from app.routes.keys import router as keys_router
from app.services.semantic_cache_cleanup_service import (
    run_semantic_cache_cleanup_loop,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    cleanup_task = asyncio.create_task(
        run_semantic_cache_cleanup_loop(
            stop_event,
            settings.semantic_cache_cleanup_interval_seconds,
        )
    )
    try:
        yield
    finally:
        stop_event.set()
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task


app = FastAPI(lifespan=lifespan)
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
app.include_router(analytics_router)
app.include_router(providers_router)

@app.get("/")
def root():
    return {"message": "AI proxy router running"}