import logging
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
import httpx

from app.config import settings
from app.db.models.api_key import APIKey
from app.db.models.provider import Provider
from app.db.models.request_log import RequestLog
from app.db.session import SessionLocal
from app.services.api_key_service import get_api_key
from app.schemas.chat import ChatCompletionRequest

router = APIRouter()
logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def save_request_log(
    api_key_id,
    provider_name: str,
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    latency_ms: int,
    status: int,
) -> None:
    logger.info(
        "Request log background task started api_key_id=%s status=%s",
        api_key_id,
        status,
    )
    db = SessionLocal()
    try:
        provider = (
            db.query(Provider)
            .filter(Provider.name == provider_name)
            .first()
        )
        provider_id = provider.id if provider is not None else None
        if provider is None:
            logger.warning(
                "Provider %s is not configured; saving request log with provider_id=NULL",
                provider_name,
            )

        logger.info(
            "Saving request log api_key_id=%s provider_id=%s status=%s database=%s host=%s",
            api_key_id,
            provider_id,
            status,
            db.bind.url.database if db.bind is not None else None,
            db.bind.url.host if db.bind is not None else None,
        )
        db.add(
            RequestLog(
                api_key_id=api_key_id,
                provider_id=provider_id,
                model=model,
                input_tokens=prompt_tokens or 0,
                output_tokens=completion_tokens or 0,
                latency_ms=latency_ms,
                status=str(status),
            )
        )
        db.commit()
        logger.info("Request log saved api_key_id=%s status=%s", api_key_id, status)
    except Exception:
        db.rollback()
        logger.exception("Failed to save request log")
    finally:
        db.close()


@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    api_key: APIKey = Depends(get_api_key),
):
    started_at = time.perf_counter()
    groq_api_key = settings.groq_api_key

    if not groq_api_key:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is not configured",
        )

    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json",
    }

    payload = request.model_dump()

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                GROQ_URL,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

        except httpx.HTTPStatusError as e:
            background_tasks.add_task(
                save_request_log,
                api_key.id,
                "groq",
                request.model,
                None,
                None,
                round((time.perf_counter() - started_at) * 1000),
                e.response.status_code,
            )
            raise HTTPException(
                status_code=e.response.status_code,
                detail=e.response.text,
            )

        except httpx.RequestError as e:
            background_tasks.add_task(
                save_request_log,
                api_key.id,
                "groq",
                request.model,
                None,
                None,
                round((time.perf_counter() - started_at) * 1000),
                502,
            )
            raise HTTPException(
                status_code=502,
                detail=f"Provider request failed: {str(e)}",
            )

    response_data = response.json()
    usage = response_data.get("usage") or {}
    response_model = response_data.get("model") or request.model
    background_tasks.add_task(
        save_request_log,
        api_key.id,
        "groq",
        response_model,
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
        round((time.perf_counter() - started_at) * 1000),
        response.status_code,
    )

    return response_data