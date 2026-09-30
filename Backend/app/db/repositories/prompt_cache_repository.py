from datetime import datetime
from typing import Any

from app.db.models.prompt_cache import PromptCache
from app.db.session import SessionLocal


def insert_prompt_cache(
    prompt: str,
    embedding: list[float],
    response: dict[str, Any],
    model: str,
    provider: str | None = None,
    expires_at: datetime | None = None,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            PromptCache(
                prompt=prompt,
                embedding=embedding,
                response=response,
                model=model,
                provider=provider,
                expires_at=expires_at,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
