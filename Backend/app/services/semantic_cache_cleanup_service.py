import asyncio
import logging

from app.db.repositories.prompt_cache_repository import (
    delete_expired_prompt_cache,
)

logger = logging.getLogger(__name__)


async def cleanup_expired_prompt_cache() -> int:
    return await asyncio.to_thread(delete_expired_prompt_cache)


async def run_semantic_cache_cleanup_loop(
    stop_event: asyncio.Event,
    interval_seconds: int,
) -> None:
    while not stop_event.is_set():
        try:
            deleted_count = await cleanup_expired_prompt_cache()
            logger.info(
                "Semantic cache cleanup deleted_rows=%d",
                deleted_count,
            )
        except Exception:
            logger.exception("Semantic cache cleanup failed")

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=interval_seconds,
            )
        except asyncio.TimeoutError:
            pass
